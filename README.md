# TRAFx - Vehicle Count Data System

This project is a web-based system to display, store, and analyze vehicle detection count data.

## Features

*   **Web-based UI:** A user-friendly web interface for managing and visualizing vehicle count data.
*   **Data Management:** Add, edit, and delete traffic monitoring sites and their associated data.
*   **Data Visualization:** View traffic trends through charts and graphs.
*   **Email Reporting:** Receive automated weekly summary reports via email.
*   **Cloud-native:** Deployed on Google Cloud Platform for scalability and reliability.
*   **CI/CD:** Automated deployment pipeline using Google Cloud Build.

## Tech Stack

*   **Backend:** Python, Flask
*   **Frontend:** HTML, CSS, JavaScript, Bootstrap
*   **Database:** Google Firestore
*   **Cloud Provider:** Google Cloud Platform (App Engine, Firestore, Cloud Build)
*   **Email Service:** SendGrid

## Getting Started

To run the application locally, you will need to have Python and `pip` installed. You will also need to have a Google Cloud project with a Firestore database.

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    ```
2.  **Install the dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Set up your environment variables:**
    *   You will need to set up a service account in your Google Cloud project and download the JSON key file.
    *   Set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to the path of your JSON key file.

4.  **Run the application:**
    ```bash
    python app.py
    ```

## Deployment

The application is deployed to Google App Engine using Google Cloud Build. The deployment process is defined in the `cloudbuild.yaml` file.

To deploy the application, run the following command:

```bash
gcloud builds submit --config cloudbuild.yaml
```

## API Endpoints

The application exposes the following API endpoints for interacting with the ESP32 devices:

*   `/api/record_vehicle_event` (POST): Records a vehicle count event.
    *   **Request Body:**
        ```json
        {
            "station_id": "<station-id>",
            "vehicle_count": <count>
        }
        ```
*   `/api/esp32/reboot` (POST): Records a reboot event.
    *   **Request Body:**
        ```json
        {
            "station_id": "<station-id>"
        }
        ```

## ESP32 Firmware Development

The `trafx_esp32` directory contains the firmware for the ESP32 devices. To build and flash the firmware, you will need to install the ESP-IDF (Espressif IoT Development Framework).

### Prerequisites

*   **Python:** Version 3.8 or later. Ensure it's added to your system's PATH.
*   **Git:** For cloning the ESP-IDF repository.
*   **Serial Drivers:** Install the necessary USB-to-UART bridge drivers for your ESP32 board (e.g., CP210x or FTDI drivers).

### Installing ESP-IDF

1.  **Clone the ESP-IDF repository:**
    It's recommended to clone it into a directory without spaces in its path.

    ```bash
    mkdir -p ~/esp
    cd ~/esp
    git clone --recursive https://github.com/espressif/esp-idf.git
    ```

2.  **Install the ESP-IDF Tools:**
    Navigate into the `esp-idf` directory and run the installation script.

    *   **Linux/macOS:**
        ```bash
        cd esp-idf
        ./install.sh
        ```
    *   **Windows (PowerShell):**
        ```powershell
        cd esp-idf
        .\install.ps1
        ```

3.  **Set up Environment Variables:**
    You need to set up the ESP-IDF environment variables in each new terminal session.

    *   **Linux/macOS:**
        ```bash
        . $HOME/esp/esp-idf/export.sh
        ```
    *   **Windows (PowerShell):
        ```powershell
        . $HOME/esp/esp-idf/export.ps1
        ```
    For convenience, you can add this command to your shell's profile file (e.g., `.bashrc`, `.zshrc`, or PowerShell profile) to have it run automatically.

### Building and Flashing

1.  **Navigate to the firmware directory:**
    ```bash
    cd trafx_esp32
    ```

2.  **Set the Target Chip:**
    ```bash
    idf.py set-target esp32
    ```

3.  **Configure Your Project (Optional):**
    This command opens a menu-based configuration utility.

    ```bash
    idf.py menuconfig
    ```

4.  **Build the Project:**
    ```bash
    idf.py build
    ```

5.  **Flash the Project to ESP32:**
    Replace `<PORT>` with the actual serial port of your ESP32 (e.g., `COM3` on Windows, `/dev/ttyUSB0` on Linux/macOS).

    ```bash
    idf.py -p <PORT> flash
    ```

6.  **Monitor Serial Output:**
    ```bash
    idf.py -p <PORT> monitor
    ```
    To exit the monitor, press `Ctrl+]`.

## ESP32 Simulation

The `simulate_esp32.py` script can be used to simulate an ESP32 device sending data to the application.

1.  **Install the `requests` library:**
    ```bash
    pip install requests
    ```
2.  **Get a Station ID:** Go to your application's "Manage Data" page and copy the ID of one of your sites.
3.  **Update the script:** Open the `simulate_esp32.py` file and replace `'YOUR_STATION_ID'` with the actual station ID you copied.
4.  **Run the script:**
    ```bash
    python simulate_esp32.py
    ```