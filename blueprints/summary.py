from flask import Blueprint, render_template, current_app
from datetime import datetime, date

summary_bp = Blueprint('summary', __name__, url_prefix='/summary')

@summary_bp.route('/')
def master_summary():
    stations_ref = current_app.db.collection(u'stations').where(u'deleted', u'!=', True).stream()
    active_sites_data = [doc.to_dict() for doc in stations_ref]
    year = datetime.now().year
    
    summary_data = []
    for site in active_sites_data:
        counts = site['counts']
        date_increment = site.get('date_increment', 'bimonthly')
        labels, current_index, _ = current_app.generate_labels_and_current_index(date_increment)

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
                    date_part = label.split('(')[1][:-1]
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

        summary_data.append({
            'site_name': site['name'],
            'monthly_totals': monthly_totals,
            'adt': f"{adt:.2f}",
            'adt_x_365': adt * 365, # Annualized ADT
            'days_with_data': days_with_data
        })

    return render_template('summary.html', year=year, summary_data=summary_data)
