from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
import pytz
from google.cloud import firestore

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route("/logs")
def get_logs():
    timezone_str = request.args.get('timezone', default=current_app.config['TIMEZONE'], type=str)
    try:
        timezone = pytz.timezone(timezone_str)
    except pytz.UnknownTimeZoneError:
        return jsonify({"error": "Unknown timezone"}), 400

    db = current_app.db
    device_logs_ref = db.collection(u'DeviceLogs').order_by(u'timestamp', direction=firestore.Query.DESCENDING).stream()
    stations_ref = db.collection(u'stations')

    logs = [log.to_dict() for log in device_logs_ref]

    station_names = {}
    for log in logs:
        if log['station_id'] not in station_names:
            station_doc = stations_ref.document(log['station_id']).get()
            if station_doc.exists:
                station_names[log['station_id']] = station_doc.to_dict().get("name", "Unknown Station")
            else:
                station_names[log['station_id']] = "Unknown Station"

    formatted_logs = []
    for log in logs:
        # Convert timestamp to the requested timezone
        utc_timestamp = log['timestamp'].replace(tzinfo=pytz.UTC)
        local_timestamp = utc_timestamp.astimezone(timezone)

        formatted_logs.append({
            "station_name": station_names.get(log['station_id'], "Unknown Station"),
            "event_type": log['event_type'],
            "timestamp": local_timestamp.strftime("%Y-%m-%d %I:%M:%S %p"),
            "timezone": timezone_str,
            "details": {
                "vehicle_count_increment": log.get('vehicle_count_increment'),
                "current_total_count": log.get('current_total_count')
            }
        })

    return jsonify(formatted_logs)


@api_bp.route("/record_vehicle_event", methods=["POST"])
def record_vehicle_event():
    data = request.get_json()
    if not data or "station_id" not in data or "vehicle_count" not in data:
        return jsonify({"error": "Missing station_id or vehicle_count"}), 400

    station_id = data["station_id"]
    vehicle_count = int(data["vehicle_count"])
    battery_level = data.get("battery_level")

    doc_ref = current_app.db.collection(u'stations').document(station_id)
    station = doc_ref.get()

    if not station.exists:
        return jsonify({"error": "Station not found"}), 404

    station_dict = station.to_dict()
    date_increment = station_dict.get("date_increment", "daily")

    _, current_index, _ = current_app.generate_labels_and_current_index(date_increment)

    if current_index == -1:
        return jsonify({"error": f"Could not determine current index for date_increment '{date_increment}'"}), 500

    # Atomically increment the count at the correct index
    counts = station_dict.get('counts', [])
    if current_index < len(counts):
        counts[current_index] += vehicle_count
    else:
        # This should not happen if the counts array is initialized correctly
        return jsonify({"error": "Index out of bounds"}), 500

    timezone = pytz.timezone(current_app.config['TIMEZONE'])
    now = datetime.now(timezone)

    update_data = {u'counts': counts, u'last_data_collection_time': now}
    if battery_level is not None:
        update_data[u'battery_level'] = battery_level

    doc_ref.update(update_data)

    # Record the vehicle event in DeviceLogs
    device_logs_ref = current_app.db.collection(u'DeviceLogs')
    device_logs_ref.add({
        u"station_id": station_id,
        u"event_type": "vehicle_event",
        u"timestamp": now,
        u"vehicle_count_increment": vehicle_count,
        u"current_total_count": counts[current_index]
    })

    return jsonify({"success": True})

@api_bp.route("/esp32/reboot", methods=["POST"])
def esp32_reboot():
    data = request.get_json()
    if not data or "station_id" not in data:
        return jsonify({"error": "Missing station_id"}), 400

    station_id = data["station_id"]

    doc_ref = current_app.db.collection(u'stations').document(station_id)
    station = doc_ref.get()

    if not station.exists:
        return jsonify({"error": "Station not found"}), 404

    timezone = pytz.timezone(current_app.config['TIMEZONE'])
    now = datetime.now(timezone)

    # Record the reboot event in DeviceLogs
    device_logs_ref = current_app.db.collection(u'DeviceLogs')
    device_logs_ref.add({
        u"station_id": station_id,
        u"event_type": "reboot",
        u"timestamp": now
    })

    # Update last_reboot_time in the Stations collection
    doc_ref.update({u'last_reboot_time': now})

    return jsonify({"success": True})
