from flask import Blueprint, render_template, current_app, jsonify
from google.cloud import firestore
from blueprints.auth import login_required

home_bp = Blueprint('home', __name__)

@home_bp.route('/')
@login_required
def home():
    stations_ref = current_app.db.collection(u'stations').where(u'deleted', u'!=', True).stream()
    active_sites = []
    for doc in stations_ref:
        site = doc.to_dict()
        site['id'] = doc.id
        active_sites.append(site)

    # Get all device logs
    device_logs_ref = current_app.db.collection(u'DeviceLogs').order_by(u'timestamp', direction=firestore.Query.DESCENDING).stream()
    logs_by_station = {}
    for log in device_logs_ref:
        log_data = log.to_dict()
        station_id = log_data.get('station_id')
        if station_id not in logs_by_station:
            logs_by_station[station_id] = {'reboot': None, 'vehicle_event': None}
        if log_data.get('event_type') == 'reboot' and not logs_by_station[station_id]['reboot']:
            logs_by_station[station_id]['reboot'] = log_data
        if log_data.get('event_type') == 'vehicle_event' and not logs_by_station[station_id]['vehicle_event']:
            logs_by_station[station_id]['vehicle_event'] = log_data

    for site in active_sites:
        site.setdefault('battery_level', 100) # Set default battery_level if not present
        station_logs = logs_by_station.get(site['id'], {})
        last_reboot = station_logs.get('reboot')
        last_vehicle_event = station_logs.get('vehicle_event')

        if last_reboot and last_reboot.get('timestamp'):
            site['last_reboot_time'] = last_reboot['timestamp'].isoformat()
        else:
            site['last_reboot_time'] = None

        if last_vehicle_event and last_vehicle_event.get('timestamp'):
            site['last_vehicle_event_time'] = last_vehicle_event['timestamp'].isoformat()
            site['last_vehicle_count_increment'] = last_vehicle_event.get('vehicle_count_increment', 'N/A')
        else:
            site['last_vehicle_event_time'] = None
            site['last_vehicle_count_increment'] = "N/A"

        date_increment = site.get('date_increment', 'bimonthly')
        labels, current_index, last_data_datetime = current_app.generate_labels_and_current_index(date_increment)
        site['labels'] = labels
        site['current_index'] = current_index
        site['next_collection_timestamp'] = current_app.get_next_collection_timestamp(date_increment, last_data_datetime)

    # Get the last event
    device_logs_ref = current_app.db.collection(u'DeviceLogs').order_by(u'timestamp', direction=firestore.Query.DESCENDING).limit(1).stream()
    last_event = None
    for log in device_logs_ref:
        last_event = log.to_dict()

    return render_template('home.html', sites=active_sites, last_event=last_event)

@home_bp.route('/most-recent')
@login_required
def most_recent():
    return render_template('most_recent.html')

@home_bp.route('/api/most-recent-data')
@login_required
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
