import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from apscheduler.schedulers.background import BackgroundScheduler
from flask import current_app

def send_email(subject, body, to_email):
    """Sends an email using SendGrid."""
    message = Mail(
        from_email='trafx@uta.com',
        to_emails=to_email,
        subject=subject,
        html_content=body)
    try:
        sendgrid_client = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
        response = sendgrid_client.send(message)
        print(f"Email sent successfully! Response code: {response.status_code}")
    except Exception as e:
        print(f"Failed to send email: {e}")

from datetime import datetime, date
import re

def generate_weekly_report_html(app):
    """Generates and sends the weekly vehicle count report."""
    stations_ref = app.db.collection(u'stations').where(u'deleted', u'!=', True).stream()
    app.data = [doc.to_dict() for doc in stations_ref]
    settings_ref = app.db.collection(u'email_settings').document(u'settings')
    settings = settings_ref.get()
    if settings.exists:
        settings = settings.to_dict()
    else:
        settings = {}
    recipients = settings.get('recipient_emails', ['default@example.com'])
    active_sites_data = app.data
    year = datetime.now().year

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
<h2>Most Recent Data</h2>
<table>
    <tr>
        <th>Site Name</th>
        <th>Latest Count</th>
        <th>Date</th>
        <th>Battery Level</th>
        <th>Last Reboot</th>
        <th>Last Data Collection</th>
    </tr>
"""
    for site in active_sites_data:
        labels, current_index, _ = app.generate_labels_and_current_index(site.get('date_increment', 'bimonthly'))
        latest_count = site['counts'][current_index] if 'counts' in site and current_index < len(site['counts']) else 'N/A'
        latest_label = labels[current_index] if current_index < len(labels) else 'N/A'
        battery_level = site.get('battery_level', 'N/A')
        
        last_reboot = site.get('last_reboot_time')
        last_reboot_formatted = last_reboot.strftime("%Y-%m-%d %H:%M:%S") if last_reboot else "N/A"

        last_data_collection = site.get('last_data_collection_time')
        last_data_collection_formatted = last_data_collection.strftime("%Y-%m-%d %H:%M:%S") if last_data_collection else "N/A"

        report_html += f"""
        <tr>
            <td>{site['name']}</td>
            <td>{latest_count}</td>
            <td>{latest_label}</td>
            <td>{battery_level}</td>
            <td>{last_reboot_formatted}</td>
            <td>{last_data_collection_formatted}</td>
        </tr>
        """
    report_html += "</table><br><hr><br>"

    for site in active_sites_data:
        counts = site.get('counts', [])
        date_increment = site.get('date_increment', 'bimonthly')
        
        # Recalculate formatted times for each site in this loop
        last_reboot = site.get('last_reboot_time')
        last_reboot_formatted = last_reboot.strftime("%Y-%m-%d %H:%M:%S") if last_reboot else "N/A"

        last_data_collection = site.get('last_data_collection_time')
        last_data_collection_formatted = last_data_collection.strftime("%Y-%m-%d %H:%M:%S") if last_data_collection else "N/A"

        # This function is attached to the app context in app.py
        labels, current_index, _ = app.generate_labels_and_current_index(date_increment)

        monthly_totals = [0] * 12
        total_yearly_traffic = 0
        days_with_data = 0

        current_counts = counts[:current_index + 1]

        if date_increment == "bimonthly":
            for i in range(0, len(current_counts), 2):
                month_idx = i // 2
                if month_idx < 12:
                    monthly_sum = current_counts[i] + (current_counts[i+1] if i + 1 < len(current_counts) else 0)
                    monthly_totals[month_idx] = monthly_sum
            total_yearly_traffic = sum(current_counts)
            for i, count in enumerate(current_counts):
                if count > 0:
                    month_num = (i // 2) + 1
                    if i % 2 == 0:
                        days_with_data += 15
                    else:
                        if month_num <= 12:
                            days_in_month = (date(year, month_num % 12 + 1, 1) - date(year, month_num, 1)).days if month_num < 12 else 31
                            days_with_data += (days_in_month - 15)
        elif date_increment == "monthly":
            for i, count in enumerate(current_counts):
                if i < 12:
                    monthly_totals[i] = count
            total_yearly_traffic = sum(current_counts)
            for i, count in enumerate(current_counts):
                if count > 0:
                    month_num = i + 1
                    if month_num <= 12:
                        days_in_month = (date(year, month_num % 12 + 1, 1) - date(year, month_num, 1)).days if month_num < 12 else 31
                        days_with_data += days_in_month
        elif date_increment == "weekly":
            for i, count in enumerate(current_counts):
                try:
                    label = labels[i]
                    # Extract date part from label, e.g., "Week X (Jan 01)" -> "Jan 01"
                    date_part_match = re.search(r'\((.*?)\)', label)
                    date_part = date_part_match.group(1) if date_part_match else label.split('(')[0].strip()
                    
                    # Handle cases where label might just be "Week X" without a date
                    if "Week" in date_part and not any(char.isalpha() for char in date_part):
                        # If only week number, approximate month based on week number
                        month_idx = min(11, (i // 4)) # Roughly 4 weeks per month
                    else:
                        dt_object = datetime.strptime(f"{date_part} {year}", "%b %d %Y")
                        month_idx = dt_object.month - 1
                    
                    if month_idx < 12:
                        monthly_totals[month_idx] += count
                except (IndexError, ValueError):
                    pass
            total_yearly_traffic = sum(current_counts)
            for count in current_counts:
                if count > 0:
                    days_with_data += 7
        elif date_increment == "daily":
            for i, count in enumerate(current_counts):
                try:
                    label = labels[i]
                    dt_object = datetime.strptime(f"{label} {year}", "%b %d %Y")
                    month_idx = dt_object.month - 1
                    if month_idx < 12:
                        monthly_totals[month_idx] += count
                except ValueError:
                    pass
            total_yearly_traffic = sum(current_counts)
            for count in current_counts:
                if count > 0:
                    days_with_data += 1

        adt = total_yearly_traffic / days_with_data if days_with_data > 0 else 0
        annualized_adt = adt * 365
        latest_count = current_counts[current_index] if current_index < len(current_counts) else 'N/A'

        # Append site table to the report
        report_html += f"""
        <h2>Site: {site['name']}</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Most Recent</td>
                <td>{latest_count}</td>
            </tr>
            <tr>
                <td>Battery Level</td>
                <td>{site.get('battery_level', 'N/A')}</td>
            </tr>
            <tr>
                <td>Last Reboot</td>
                <td>{last_reboot_formatted}</td>
            </tr>
            <tr>
                <td>Last Data Collection</td>
                <td>{last_data_collection_formatted}</td>
            </tr>
            <tr>
                <td>Average Daily Traffic (ADT)</td>
                <td>{adt:.2f}</td>
            </tr>
            <tr>
                <td>Annualized ADT (ADT x 365)</td>
                <td>{annualized_adt:,.2f}</td>
            </tr>
            <tr>
                <td>Total Days with Data</td>
                <td>{days_with_data}</td>
            </tr>
            <tr>
                <td>Total Vehicle Count (YTD)</td>
                <td>{total_yearly_traffic:,.0f}</td>
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
                {''.join(f'<td>{total:,.0f}</td>' for total in monthly_totals)}
            </tr>
        </table>
        <h3>Last 12 Periods</h3>
        <table>
            <tr>
                <th>Period</th>
                <th>Count</th>
            </tr>
            {''.join(f"<tr><td>{label}</td><td>{count:,.0f}</td></tr>" for label, count in zip(labels[max(0, current_index - 11):current_index + 1], counts[max(0, current_index - 11):current_index + 1]))}
        </table>
        <br><hr><br>
        """
    
    report_html += "</body></html>"
    return report_html


def generate_weekly_report(app):
    """Generates and sends the weekly vehicle count report."""
    ctx = app.app_context()
    ctx.push()
    try:
        settings_ref = app.db.collection(u'email_settings').document(u'settings')
        settings = settings_ref.get()
        if settings.exists:
            settings = settings.to_dict()
        else:
            settings = {}
        recipients = settings.get('recipient_emails', ['default@example.com'])
        report_html = generate_weekly_report_html(app)
        for recipient in recipients:
            send_email("TRAFx Weekly Summary Report", report_html, recipient)
    finally:
        ctx.pop()

# Define a global scheduler instance
scheduler = None

def init_scheduler(app):
    """Initializes and starts the scheduler."""
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown()

    with app.app_context():
        settings_ref = app.db.collection(u'email_settings').document(u'settings')
        settings = settings_ref.get()
        if settings.exists:
            settings = settings.to_dict()
        else:
            settings = {}
        frequency = settings.get('report_frequency', 'weekly')
        day_of_week = settings.get('day_of_week', 'mon')
        day_of_month = settings.get('day_of_month', 1)
        hour, minute = map(int, settings.get('report_time', '08:00').split(':'))

    trigger = None
    if frequency == 'daily':
        trigger = 'cron'
        trigger_args = {'hour': hour, 'minute': minute}
    elif frequency == 'weekly':
        trigger = 'cron'
        trigger_args = {'day_of_week': day_of_week, 'hour': hour, 'minute': minute}
    elif frequency == 'monthly':
        trigger = 'cron'
        trigger_args = {'day': day_of_month, 'hour': hour, 'minute': minute}

    if trigger:
        scheduler = BackgroundScheduler()
        scheduler.add_job(func=generate_weekly_report, args=[app], trigger=trigger, **trigger_args, misfire_grace_time=3600)
        scheduler.start()

        import atexit
        atexit.register(lambda: scheduler.shutdown())