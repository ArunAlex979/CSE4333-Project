import requests
import json
import random

# --- Configuration ---
# Replace with the URL of your deployed application
BASE_URL = "https://trafxcloud.uc.r.appspot.com"
# Replace with a valid station ID from your database
STATION_ID = "J7PrtYPaRs9yL9xatx9p"
# ---------------------

def record_vehicle_event(vehicle_count, battery_level):
    """Simulates an ESP32 sending a vehicle count event with battery level."""
    url = f"{BASE_URL}/api/record_vehicle_event"
    data = {
        "station_id": STATION_ID,
        "vehicle_count": vehicle_count,
        "battery_level": battery_level
    }
    headers = {'Content-Type': 'application/json'}

    try:
        response = requests.post(url, data=json.dumps(data), headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes
        print(f"Successfully recorded {vehicle_count} vehicle(s) and battery level {battery_level}% for station {STATION_ID}.")
        print("Response:", response.json())
    except requests.exceptions.RequestException as e:
        print(f"Error recording vehicle event: {e}")

if __name__ == "__main__":
    # --- Simulate a vehicle event with a random battery level ---
    random_battery_level = random.randint(0, 100)
    record_vehicle_event(5, random_battery_level)
