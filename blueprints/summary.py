from flask import Blueprint, render_template, current_app
from datetime import datetime, date
from blueprints.auth import login_required

summary_bp = Blueprint('summary', __name__, url_prefix='/summary')

def calculate_summary_data(sites_data, year):
    summary_data = []
    for site in sites_data:
        counts = site['counts']
        date_increment = site.get('date_increment', 'bimonthly')
        labels, _, _ = current_app.generate_labels_and_current_index(date_increment, year=year)

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
            'site_name': site['name'],
            'monthly_totals': monthly_totals,
            'adt': f"{adt:.2f}",
            'adt_x_365': adt * 365,
            'days_with_data': int(days_with_data)
        })
    return summary_data

@summary_bp.route('/')
@login_required
def master_summary():
    stations_ref = current_app.db.collection(u'stations').where(u'deleted', u'!=', True).stream()
    active_sites_data = [doc.to_dict() for doc in stations_ref]
    
    # Get all unique years from the data
    years = set()
    for site in active_sites_data:
        try:
            start_date = datetime.strptime(site['start_date'], '%Y-%m-%d')
            years.add(start_date.year)
        except (ValueError, KeyError):
            continue
    
    summary_data_by_year = {}
    for year in sorted(list(years)):
        sites_in_year = [site for site in active_sites_data if datetime.strptime(site['start_date'], '%Y-%m-%d').year == year]
        summary_data_by_year[year] = calculate_summary_data(sites_in_year, year)

    return render_template('summary.html', summary_data_by_year=summary_data_by_year)
