import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date, timedelta
import pytz
from google.cloud import firestore

# Initialize Firestore client
db = firestore.Client()

# --- Functions adapted from app.py and blueprints/summary.py ---

def generate_labels_and_current_index(date_increment="bimonthly", year=None):
    labels = []
    # Use environment variable for timezone or default
    timezone = pytz.timezone(os.environ.get('TIMEZONE', 'America/Chicago'))
    current_date = datetime.now(timezone)
    if year is None:
        year = current_date.year

    current_index = -1
    last_data_datetime = None

    is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
    days_in_year = 366 if is_leap else 365

    if date_increment == "daily":
        for i in range(days_in_year):
            d = datetime(year, 1, 1) + timedelta(days=i)
            labels.append(d.strftime('%b %d'))
            if d.date() == current_date.date():
                current_index = i
                last_data_datetime = d
    elif date_increment == "weekly":
        for i in range(52):
            d = datetime(year, 1, 1) + timedelta(weeks=i)
            labels.append(f"Week {i+1} ({d.strftime('%b %d')})")
            if d.isocalendar()[1] == current_date.isocalendar()[1] and d.year == year:
                current_index = i
                last_data_datetime = d
    elif date_increment == "monthly":
        for month in range(1, 13):
            d = date(year, month, 1)
            labels.append(d.strftime('%b'))
            if current_date.year == year and current_date.month == month:
                current_index = month - 1
                last_data_datetime = datetime(d.year, d.month, d.day)
    elif date_increment == "bimonthly":
        for month in range(1, 13):
            date1 = date(year, month, 1)
            labels.append(f"{date1.day} {date1.strftime('%b')}")
            if current_date.year == year and current_date.month == month and current_date.day < 15:
                current_index = len(labels) - 1
                last_data_datetime = datetime(date1.year, date1.month, date1.day)

            date2 = date(year, month, 15)
            labels.append(f"{date2.day} {date2.strftime('%b')}")
            if current_date.year == year and current_date.month == month and current_date.day >= 15:
                current_index = len(labels) - 1
                last_data_datetime = datetime(date2.year, date2.month, date2.day)
    return labels, current_index, last_data_datetime


def calculate_summary_data(sites_data, year):
    summary_data = []
    for site in sites_data:
        counts = site.get('counts', []) # Use .get with default empty list
        date_increment = site.get('date_increment', 'bimonthly')
        
        # Call the local generate_labels_and_current_index
        labels, _, _ = generate_labels_and_current_index(date_increment, year=year)

        monthly_totals = [0] * 12
        total_yearly_traffic = 0
        days_with_data = 0

        if date_increment == "daily":
            for i, count in enumerate(counts):
                if count > 0:
                    days_with_data += 1
                    total_yearly_traffic += count
                    month_index = int(i / (365.25 / 12))
                    if month_index < 12:
                        monthly_totals[month_index] += count
        elif date_increment == "weekly":
            for i, count in enumerate(counts):
                if count > 0:
                    days_with_data += 7
                    total_yearly_traffic += count
                    month_index = int(i / (52 / 12))
                    if month_index < 12:
                        monthly_totals[month_index] += count
        elif date_increment == "monthly":
            for i, count in enumerate(counts):
                if count > 0:
                    days_with_data += 30 # Approximation
                    total_yearly_traffic += count
                    if i < 12:
                        monthly_totals[i] += count
        elif date_increment == "bimonthly":
            for i, count in enumerate(counts):
                if count > 0:
                    days_with_data += 15 # Approximation
                    total_yearly_traffic += count
                    month_index = int(i / 2)
                    if month_index < 12:
                        monthly_totals[month_index] += count
                        
        adt = total_yearly_traffic / days_with_data if days_with_data > 0 else 0

        summary_data.append({
            'site_name': site.get('name', 'Unknown Site'),
            'monthly_totals': monthly_totals,
            'adt': f"{adt:.2f}",
            'adt_x_365': adt * 365,
            'days_with_data': int(days_with_data)
        })
    return summary_data


def generate_weekly_report_html():
    """Generates the weekly vehicle count report HTML."""
    stations_ref = db.collection(u'stations').where(u'deleted', u'!=', True).stream()
    active_sites_data = [doc.to_dict() for doc in stations_ref]
    year = datetime.now().year # Reports for the current year

    summary_data = calculate_summary_data(active_sites_data, year)

    # Start of the HTML report with some basic styling
    report_html = f"""
<html>
<head>
<style>
    body {{ font-family: sans-serif; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #dddddd; text-align: left; padding: 8px; }}
    th {{ background-color: #f2f2f2; }}
    tr:nth-child(even) {{ background-color: #f9f9f9; }}
    h1, h2 {{ color: #333; }}
</style>
</head>
<body>
<h1>TRAFx Weekly Summary Report - {date.today().strftime('%Y-%m-%d')}</h1>
"""

    for site_summary in summary_data:
        report_html += f"""
        <h2>Site: {site_summary['site_name']}</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Average Daily Traffic (ADT)</td>
                <td>{site_summary['adt']}</td>
            </tr>
            <tr>
                <td>Annualized ADT (ADT x 365)</td>
                <td>{site_summary['adt_x_365']:,.2f}</td>
            </tr>
            <tr>
                <td>Total Days with Data</td>
                <td>{site_summary['days_with_data']}</td>
            </tr>
            <tr>
                <td>Total Vehicle Count (YTD)</td>
                <td>{sum(site_summary['monthly_totals']):,.0f}</td>
            </tr>
        </table>
        <h3>Monthly Totals ({year})</h3>
        <table>
            <tr>
                <th>Jan</th><th>Feb</th><th>Mar</th><th>Apr</th>
                <th>May</th><th>Jun</th><th>Jul</th><th>Aug</th>
                <th>Sep</th><th>Oct</th><th>Nov</th><th>Dec</th>
            </tr>
            <tr>
                {''.join(f'<td>{total:,.0f}</td>' for total in site_summary['monthly_totals'])}
            </tr>
        </table>
        <br><hr><br>
        """
    
    report_html += "</body></html>"
    return report_html


def send_email(subject, body, to_email):
    """Sends an email using SMTP."""
    sender_email = os.environ.get("SENDER_EMAIL")
    password = os.environ.get("SENDER_PASSWORD")

    if not sender_email or not password:
        print("SENDER_EMAIL or SENDER_PASSWORD environment variables not set.")
        raise ValueError("Email credentials not configured.")

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, password)
        text = msg.as_string()
        server.sendmail(sender_email, to_email, text)
        server.quit()
        print(f"Email sent successfully to {to_email}!")
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")
        raise


# --- Cloud Function Entry Point ---

def send_weekly_report_cf(request):
    """
    Cloud Function to generate and send weekly traffic reports.
    Triggered by Cloud Scheduler.
    """
    print("Cloud Function 'send_weekly_report_cf' triggered.")

    try:
        # Fetch email settings from Firestore
        settings_ref = db.collection(u'email_settings').document(u'settings')
        settings = settings_ref.get()
        if settings.exists:
            settings = settings.to_dict()
        else:
            settings = {}
            print("No email settings found in Firestore. Using default recipients.")
        
        # Get recipient emails, defaulting to a placeholder if none are configured
        recipients = settings.get('recipient_emails', ['default@example.com'])
        if not recipients or recipients == ['default@example.com']:
            print("No valid recipient emails configured. Aborting email send.")
            return "No recipients configured."

        # Generate the report HTML
        report_html = generate_weekly_report_html()

        # Send emails to all recipients
        for recipient in recipients:
            send_email("TRAFx Weekly Summary Report (Cloud Function)", report_html, recipient)
        
        return "Weekly report emails sent successfully."

    except Exception as e:
        print(f"Error in Cloud Function: {e}")
        # In a real-world scenario, you might want to log this error to Stackdriver Error Reporting
        # or send an alert.
        raise