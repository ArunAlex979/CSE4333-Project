from flask import Blueprint, render_template, current_app, jsonify

home_bp = Blueprint('home', __name__)

@home_bp.route('/')
def home():
    stations_ref = current_app.db.collection(u'stations').where(u'deleted', u'!=', True).stream()
    active_sites = []
    for doc in stations_ref:
        site = doc.to_dict()
        site['id'] = doc.id
        active_sites.append(site)

    for site in active_sites:
        site.setdefault('battery_level', 100) # Set default battery_level if not present
        
        # Format last_reboot_time and last_data_collection_time for display
        if 'last_reboot_time' in site and site['last_reboot_time']:
            site['last_reboot_time_formatted'] = site['last_reboot_time'].strftime("%Y-%m-%d %H:%M:%S")
        else:
            site['last_reboot_time_formatted'] = "N/A"

        if 'last_data_collection_time' in site and site['last_data_collection_time']:
            site['last_data_collection_time_formatted'] = site['last_data_collection_time'].strftime("%Y-%m-%d %H:%M:%S")
        else:
            site['last_data_collection_time_formatted'] = "N/A"

        date_increment = site.get('date_increment', 'bimonthly')
        labels, current_index, last_data_datetime = current_app.generate_labels_and_current_index(date_increment)
        site['labels'] = labels
        site['current_index'] = current_index
        site['next_collection_timestamp'] = current_app.get_next_collection_timestamp(date_increment, last_data_datetime)

    return render_template('home.html', sites=active_sites)

@home_bp.route('/most-recent')
def most_recent():
    return render_template('most_recent.html')

@home_bp.route('/api/most-recent-data')
def most_recent_data():
    stations_ref = current_app.db.collection(u'stations').where(u'deleted', u'!=', True).stream()
    active_sites = []
    for doc in stations_ref:
        site = doc.to_dict()
        site['id'] = doc.id
        active_sites.append(site)

    for site in active_sites:
        site.setdefault('battery_level', 100) # Set default battery_level if not present
    
    for site in active_sites:
        date_increment = site.get('date_increment', 'bimonthly')
        labels, current_index, last_data_datetime = current_app.generate_labels_and_current_index(date_increment)
        site['labels'] = labels
        site['current_index'] = current_index
        site['next_collection_timestamp'] = current_app.get_next_collection_timestamp(date_increment, last_data_datetime)

    return jsonify(sites=active_sites)
