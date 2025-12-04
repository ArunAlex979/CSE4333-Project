# TRAFx ESP32 Email Setup and System Overview

This document provides instructions on how to set up the email functionality for the TRAFx ESP32 device and an overview of how the system works.

## Email Setup

To enable the email functionality, you need to configure the SMTP settings in the `menuconfig`.

1.  **Open `menuconfig`:**

    ```bash
    idf.py menuconfig
    ```

2.  **Navigate to SMTP Configuration:**

    Go to `Component config` -> `TRAFx Configuration` -> `SMTP Configuration`

3.  **Configure the following settings:**

    *   **SMTP Server:** The address of your SMTP server (e.g., `smtp.gmail.com`).
    *   **SMTP Port:** The port of your SMTP server (e.g., `465` for SSL).
    *   **SMTP Username:** Your email address.
    *   **SMTP Password:** Your email password or an app-specific password. **For Gmail, you will likely need to generate an App Password.** See the Troubleshooting section for more details.
    *   **Recipient Email:** The email address(es) where you want to receive the reports. You can specify multiple recipients by separating them with commas (e.g., `email1@example.com,email2@example.com`).

4.  **Save and Exit:**

    Save your configuration and exit `menuconfig`.

5.  **Build and Flash:**

    Build and flash the firmware to your ESP32 device:

    ```bash
    idf.py build
    idf.py -p (Your Port) flash
    ```

## System Overview

The TRAFx ESP32 device is designed to count vehicles and send periodic reports via email. Here's a breakdown of how it works:

### Vehicle Counting

*   A GPIO pin is configured to detect rising edge interrupts, which are triggered by a sensor when a vehicle passes.
*   Each time an interrupt occurs, a counter is incremented.
*   The vehicle count is stored in Non-Volatile Storage (NVS) to persist across reboots.
*   Vehicle counting starts immediately upon device boot, even before network or time synchronization is complete.

### Time Synchronization

*   The ESP32 connects to a Wi-Fi network.
*   It uses the Simple Network Time Protocol (SNTP) to obtain the current time from a time server.
*   The device will continuously retry time synchronization every 60 seconds until successful.
*   The time is used to schedule the email reports and to timestamp the data.

### Scheduled Reporting

*   A task runs in the background to send email reports at a configurable interval (`daily`, `weekly`, or `monthly`).
*   The time of day for the report is also configurable.
*   When it's time to send a report, the device retrieves the vehicle count from NVS.

### Email Reporting and Data Archival

To ensure data is never lost due to network failures, the device features a data archival system.

*   **Email Composition:** The device establishes a secure TLS connection to the configured SMTP server and authenticates. It then constructs and sends an email containing one or more reports.

*   **Vehicle Count Report:** This email is sent on a schedule and includes the following sections:
    *   **--- Current Report ---**
        *   **Site Name:** The ID of the station.
        *   **Count:** The number of vehicles counted for the most recent reporting period.
        *   **Start Date / End Date:** The time window for the current report.
    *   **--- Archived Reports (if any) ---**
        *   If the device was unable to send previous reports, they are stored in memory.
        *   This section will list each previously failed report, with its specific vehicle count and time period.
    *   **--- Scheduling Info ---**
        *   **Report Interval:** The configured interval (e.g., daily).
        *   **Scheduled Time:** The time of day reports are sent.
        *   **Time until next send:** A countdown to the next report.
        *   **Next data send:** The timestamp of the next report.
        *   **Timezone:** The timezone string the device is configured to use.

*   **Reboot Notification Email:** A simpler email is sent when the device reboots. It includes a timestamp, the current unsent vehicle count, any archived reports, and the timezone.

*   **Data Persistence Logic:**
    *   If an email (either scheduled or reboot) is sent **successfully**, any archived reports included in it are deleted from the device's memory. The current vehicle count is reset to 0.
    *   If an email **fails** to send, the report for the current period is added to the archive for the next attempt. This ensures that no vehicle counts are ever lost.

---

## Troubleshooting

### Warning: Flash Size Mismatch

During the build/flash process, you might encounter the following warning:

```
W (534) spi_flash: Detected size(16384k) larger than the size in the binary image header(2048k). Using the size in the binary image header.
```

**Explanation:** This warning indicates that your ESP32 board has a 16MB flash chip, but the project configuration is set to use only 2MB. While this doesn't prevent the application from running, it means 14MB of your flash storage is unused.

**Solution:** To utilize the full 16MB flash, you should update your project configuration:

1.  Run `idf.py menuconfig` in your project directory.
2.  Navigate to **Serial flasher config**.
3.  Select **Flash size**.
4.  Change the value from `2MB` to **16MB**.
5.  Press **S** to save the configuration.
6.  Press **Q** to quit the menu.
7.  After saving and exiting, rebuild and re-flash your project:
    ```bash
    idf.py build flash monitor
    ```
    This will apply the new flash size configuration, and the warning should no longer appear.

---

### Error: Stack Overflow

After enabling email functionality, you might encounter a stack overflow error that causes the device to reboot continuously:

```
***ERROR*** A stack overflow in task main has been detected.
```

**Explanation:** This error occurs because sending an email, especially with a secure connection (TLS), requires a large amount of stack memory. The default memory allocated to the main application task is not sufficient.

**Solution:** To fix this, you need to increase the stack size for the main task:

1.  Run `idf.py menuconfig` in your project directory.
2.  Navigate to **Component config**.
3.  Navigate to **ESP System Settings**.
4.  Find **Main task stack size** and change its value from the default (e.g., `3584`) to `8192`.
5.  Press **S** to save the configuration.
6.  Press **Q** to quit the menu.
7.  After saving and exiting, rebuild and re-flash your project:
    ```bash
    idf.py build flash monitor
    ```
    This will resolve the stack overflow and allow the device to boot and send emails correctly.

---

### Troubleshooting Email Authentication (Gmail Specific)

If you encounter `535-5.7.8 Username and Password not accepted` or `530-5.7.0 Authentication Required` errors in your logs when trying to send emails, especially with Gmail, it's likely due to Google's security policies.

**Explanation:** Modern email providers like Gmail often block attempts to log in from "less secure apps" or devices using your primary account password.

**Solution:** You need to generate an "App Password" for your Google account and use that instead of your regular password in the ESP32's SMTP configuration.

1.  Go to your Google Account (myaccount.google.com).
2.  Navigate to **Security**.
3.  Under "How you sign in to Google", enable **2-Step Verification** if it's not already enabled (this is a prerequisite for App Passwords).
4.  Once 2-Step Verification is on, you should see an **App passwords** option. Click on it.
5.  You may need to re-enter your Google password.
6.  Select the app and device you want to generate the password for. For "Select app", choose **Mail**. For "Select device", choose **Other (Custom name)** and enter a name like "ESP32 TRAFx".
7.  Click **Generate**.
8.  Google will display a 16-character password. **Copy this password.** This is the password you will use in the ESP32's `menuconfig` for **SMTP Password**.
9.  Update the **SMTP Password** in `idf.py menuconfig` with this generated App Password.
10. Save, build, and flash your project.

Using an App Password will allow your ESP32 device to authenticate successfully with Gmail's SMTP server.

---

## Network Configuration

### Enabling PPP Support for Cellular Modems

If you are using a cellular modem (like the SIM7600) instead of WiFi, you need to enable PPP (Point-to-Point Protocol) support in the project configuration.

1.  **Open `menuconfig`:**

    ```bash
    idf.py menuconfig
    ```

2.  **Navigate to LWIP Configuration:**

    Go to `Component config` -> `LWIP`

3.  **Enable PPP Support:**

    Find and enable the `Enable PPP support` option.

4.  **Save and Exit:**

    Save your configuration and exit `menuconfig`.

5.  **Build and Flash:**

    Build and flash the firmware to your ESP32 device.