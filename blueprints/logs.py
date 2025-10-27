from flask import Blueprint, render_template, current_app
from datetime import datetime
from google.cloud import firestore

logs_bp = Blueprint('logs', __name__, url_prefix='/logs')

@logs_bp.route('/')
def view_logs():
    db = current_app.db
    device_logs_ref = db.collection(u'DeviceLogs').order_by(u'timestamp', direction=firestore.Query.DESCENDING).stream()
    stations_ref = db.collection(u'Stations')

    # Fetch all logs
    logs = [log.to_dict() for log in device_logs_ref]

    # Fetch station names for display
    station_names = {}
    for log in logs:
        if log['station_id'] not in station_names:
            station_doc = stations_ref.document(log['station_id']).get()
            if station_doc.exists:
                station_names[log['station_id']] = station_doc.to_dict().get("name", "Unknown Station")
            else:
                station_names[log['station_id']] = "Unknown Station"

    # Format logs for display
    formatted_logs = []
    for log in logs:
        formatted_logs.append({
            "station_name": station_names.get(log['station_id'], "Unknown Station"),
            "event_type": log['event_type'],
            "timestamp": log['timestamp'].strftime("%Y-%m-%d %H:%M:%S"),
            "details": {
                "vehicle_count_increment": log.get('vehicle_count_increment'),
                "current_total_count": log.get('current_total_count')
            }
        })

    return render_template('logs.html', logs=formatted_logs)
