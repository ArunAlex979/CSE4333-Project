from flask import Flask, request, jsonify
from pymongo import MongoClient, ReturnDocument
from datetime import date, datetime, timedelta
from bson.objectid import ObjectId

app = Flask(__name__)

# --- Configuration ---
MONGO_URI = "mongodb+srv://trafx-user:password@trafx.elditss.mongodb.net/?retryWrites=true&w=majority&appName=TRAFx"
DATABASE_NAME = "TRAFX"
COLLECTION_NAME = "Stations"
# ---------------------

client = MongoClient(MONGO_URI)
db = client[DATABASE_NAME]
collection = db[COLLECTION_NAME]
device_logs_collection = db["DeviceLogs"]

@app.route("/esp32/reboot", methods=["POST"])
def esp32_reboot():
    data = request.get_json()
    if not data or "station_id" not in data:
        return jsonify({"error": "Missing station_id"}), 400

    station_id = data["station_id"]

    try:
        station_oid = ObjectId(station_id)
    except Exception:
        return jsonify({"error": "Invalid station_id"}), 400

    # Record the reboot event in DeviceLogs
    device_logs_collection.insert_one({
        "station_id": station_oid,
        "event_type": "reboot",
        "timestamp": datetime.now()
    })

    # Update last_reboot_time in the Stations collection
    collection.update_one(
        {"_id": station_oid},
        {"$set": {"last_reboot_time": datetime.now()}}
    )

    # Get station name for logging
    station = collection.find_one({"_id": station_oid})
    station_name = station.get("name", "Unknown Station") if station else "Unknown Station"

    print(f"ESP32 station '{station_name}' (ID: {station_id}) rebooted at {datetime.now()}")
    return jsonify({"success": True})

# --- Date Logic (copied from app.py) ---
def generate_labels_and_current_index(date_increment="bimonthly"):
    labels = []
    current_date = datetime.now()
    current_index = -1
    last_data_datetime = None

    if date_increment == "daily":
        for i in range(365):
            d = datetime(current_date.year, 1, 1) + timedelta(days=i)
            labels.append(d.strftime('%b %d'))
            if d.date() == current_date.date():
                current_index = i
                last_data_datetime = d
    elif date_increment == "weekly":
        for i in range(52):
            d = datetime(current_date.year, 1, 1) + timedelta(weeks=i)
            labels.append(f"Week {i+1} ({d.strftime('%b %d')})")
            if d.isocalendar()[1] == current_date.isocalendar()[1] and d.year == current_date.year:
                current_index = i
                last_data_datetime = d
    elif date_increment == "monthly":
        for month in range(1, 13):
            d = date(current_date.year, month, 1)
            labels.append(d.strftime('%b'))
            if current_date.month == month:
                current_index = month - 1
                last_data_datetime = datetime(d.year, d.month, d.day)
    elif date_increment == "bimonthly":
        for month in range(1, 13):
            date1 = date(current_date.year, month, 1)
            labels.append(f"{date1.day} {date1.strftime('%b')}")
            if current_date.month == month and current_date.day < 15:
                current_index = len(labels) - 1
                last_data_datetime = datetime(date1.year, date1.month, date1.day)

            date2 = date(current_date.year, month, 15)
            labels.append(f"{date2.day} {date2.strftime('%b')}")
            if current_date.month == month and current_date.day >= 15:
                current_index = len(labels) - 1
                last_data_datetime = datetime(date2.year, date2.month, date2.day)
    return labels, current_index, last_data_datetime
# ----------------------------------------

@app.route("/record_vehicle_event", methods=["POST"])
def record_vehicle_event():
    data = request.get_json()
    if not data or "station_id" not in data or "vehicle_count" not in data:
        return jsonify({"error": "Missing station_id or vehicle_count"}), 400

    station_id = data["station_id"]
    vehicle_count = int(data["vehicle_count"])

    try:
        station_oid = ObjectId(station_id)
    except Exception:
        return jsonify({"error": "Invalid station_id"}), 400

    # 1. Find the station to get its date_increment setting
    station = collection.find_one({"_id": station_oid})
    if not station:
        return jsonify({"error": "Station not found"}), 404

    date_increment = station.get("date_increment", "daily") # Default to daily

    # 2. Calculate the correct index for today
    _, current_index, _ = generate_labels_and_current_index(date_increment)

    if current_index == -1:
        return jsonify({"error": f"Could not determine current index for date_increment '{date_increment}'"}), 500

    # 3. Atomically increment the count at the correct index by vehicle_count
    field_to_increment = f"counts.{current_index}"
    result = collection.update_one(
        {"_id": station_oid},
        {"$inc": {field_to_increment: vehicle_count}}
    )

    # 4. (Optional) For logging, get the updated count
    updated_station = collection.find_one({"_id": station_oid})
    current_count = updated_station['counts'][current_index] if updated_station and 'counts' in updated_station and len(updated_station['counts']) > current_index else 'N/A'

    station_name = station.get("name", "N/A")
    print(f"Logged event for '{station_name}'. Incremented index {current_index} by {vehicle_count}. New count: {current_count}")

    # Update last_data_collection_time in the Stations collection
    collection.update_one(
        {"_id": station_oid},
        {"$set": {"last_data_collection_time": datetime.now()}}
    )

    # Record the vehicle event in DeviceLogs
    device_logs_collection.insert_one({
        "station_id": station_oid,
        "event_type": "vehicle_event",
        "timestamp": datetime.now(),
        "vehicle_count_increment": vehicle_count,
        "current_total_count": current_count # Log the total count after increment
    })

    return jsonify({"success": True})


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
