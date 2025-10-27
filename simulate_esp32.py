import requests
import json

# --- Configuration ---
# Replace with the URL of your deployed application
BASE_URL = "https://trafxcloud.uc.r.appspot.com"
# Replace with a valid station ID from your database
STATION_ID = "kqxhEQMyv1UKJAlSHkN3"
# ---------------------

def record_vehicle_event(vehicle_count):
    """Simulates an ESP32 sending a vehicle count event."""
    url = f"{BASE_URL}/api/record_vehicle_event"
    data = {
        "station_id": STATION_ID,
        "vehicle_count": vehicle_count
    }
    headers = {'Content-Type': 'application/json'}

    try:
        response = requests.post(url, data=json.dumps(data), headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes
        print(f"Successfully recorded {vehicle_count} vehicle(s) for station {STATION_ID}.")
        print("Response:", response.json())
    except requests.exceptions.RequestException as e:
        print(f"Error recording vehicle event: {e}")

def reboot():
    """Simulates an ESP32 sending a reboot event."""
    url = f"{BASE_URL}/api/esp32/reboot"
    data = {
        "station_id": STATION_ID
    }
    headers = {'Content-Type': 'application/json'}

    try:
        response = requests.post(url, data=json.dumps(data), headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes
        print(f"Successfully recorded reboot for station {STATION_ID}.")
        print("Response:", response.json())
    except requests.exceptions.RequestException as e:
        print(f"Error recording reboot event: {e}")

if __name__ == "__main__":
    # --- Simulate a vehicle event ---
    record_vehicle_event(1)

    # --- Simulate a reboot event ---
    # reboot()
