from flask import Blueprint, request, jsonify, current_app
from datetime import datetime

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route("/record_vehicle_event", methods=["POST"])
def record_vehicle_event():
    data = request.get_json()
    if not data or "station_id" not in data or "vehicle_count" not in data:
        return jsonify({"error": "Missing station_id or vehicle_count"}), 400

    station_id = data["station_id"]
    vehicle_count = int(data["vehicle_count"])

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

    doc_ref.update({u'counts': counts, u'last_data_collection_time': datetime.now()})

    # Record the vehicle event in DeviceLogs
    device_logs_ref = current_app.db.collection(u'DeviceLogs')
    device_logs_ref.add({
        u"station_id": station_id,
        u"event_type": "vehicle_event",
        u"timestamp": datetime.now(),
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

    # Record the reboot event in DeviceLogs
    device_logs_ref = current_app.db.collection(u'DeviceLogs')
    device_logs_ref.add({
        u"station_id": station_id,
        u"event_type": "reboot",
        u"timestamp": datetime.now()
    })

    # Update last_reboot_time in the Stations collection
    doc_ref.update({u'last_reboot_time': datetime.now()})

    return jsonify({"success": True})
