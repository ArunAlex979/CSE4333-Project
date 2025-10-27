#include <string.h>
#include <inttypes.h>
#include <time.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "esp_event.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "nvs.h"
#include "esp_http_client.h"
#include "driver/gpio.h"
#include "esp_timer.h"
#include "esp_sntp.h"
#include "wifi.h"

#define TAG "main"

// --- Configuration ---
#define API_ENDPOINT_URL "http://10.0.0.20:5000/record_vehicle_event"
#define STATION_ID "68e9b597390df31a18fcafea" // Example ID - CHANGE THIS
#define STORAGE_NAMESPACE "storage"

// -- Scheduling Configuration --
// Set the desired interval: "daily", "weekly", or "monthly"
#define SEND_INTERVAL "daily"
// Set the time of day for the daily report (24-hour format)
#define SEND_HOUR 16 // 4 PM
#define SEND_MINUTE 16 // 30 minutes past the hour
// Set your timezone here, e.g., "CST6CDT,M3.2.0,M11.1.0" for US Central Time
#define TIMEZONE "CST6CDT,M3.2.0,M11.1.0"
// --------------------

static QueueHandle_t gpio_events = NULL;
static uint32_t vehicle_count = 0;
static time_t last_send_time = 0;
static uint64_t last_gpio_time = 0;

// --- NVS Functions ---
void init_nvs() {
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);
}

void read_u32_from_nvs(const char* key, uint32_t* value) {
    nvs_handle_t my_handle;
    esp_err_t err = nvs_open(STORAGE_NAMESPACE, NVS_READWRITE, &my_handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Error opening NVS handle for key: %s", key);
        return;
    }

    err = nvs_get_u32(my_handle, key, value);
    switch (err) {
        case ESP_OK:
            ESP_LOGI(TAG, "Successfully read %s from NVS: %lu", key, (long unsigned int)*value);
            break;
        case ESP_ERR_NVS_NOT_FOUND:
            ESP_LOGI(TAG, "%s not found in NVS, initializing to 0", key);
            *value = 0;
            break;
        default:
            ESP_LOGE(TAG, "Error reading %s from NVS!", key);
    }
    nvs_close(my_handle);
}

void write_u32_to_nvs(const char* key, uint32_t value) {
    nvs_handle_t my_handle;
    esp_err_t err = nvs_open(STORAGE_NAMESPACE, NVS_READWRITE, &my_handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Error opening NVS handle for key: %s", key);
        return;
    }

    esp_err_t err_set = nvs_set_u32(my_handle, key, value);
    if (err_set != ESP_OK) {
        ESP_LOGE(TAG, "Failed to write %s to NVS!", key);
    }

    esp_err_t err_commit = nvs_commit(my_handle);
    if (err_commit != ESP_OK) {
        ESP_LOGE(TAG, "Failed to commit %s to NVS!", key);
    } else {
        ESP_LOGI(TAG, "Saved %s to NVS: %lu", key, (long unsigned int)value);
    }
    
    nvs_close(my_handle);
}

void read_time_from_nvs(const char* key, time_t* value) {
    nvs_handle_t my_handle;
    esp_err_t err = nvs_open(STORAGE_NAMESPACE, NVS_READWRITE, &my_handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Error opening NVS handle for key: %s", key);
        return;
    }

    err = nvs_get_i64(my_handle, key, (int64_t*)value);
    switch (err) {
        case ESP_OK:
            ESP_LOGI(TAG, "Successfully read %s from NVS", key);
            break;
        case ESP_ERR_NVS_NOT_FOUND:
            ESP_LOGI(TAG, "%s not found in NVS, initializing to 0", key);
            *value = 0;
            break;
        default:
            ESP_LOGE(TAG, "Error reading %s from NVS!", key);
    }
    nvs_close(my_handle);
}

void write_time_to_nvs(const char* key, time_t value) {
    nvs_handle_t my_handle;
    esp_err_t err = nvs_open(STORAGE_NAMESPACE, NVS_READWRITE, &my_handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Error opening NVS handle for key: %s", key);
        return;
    }

    esp_err_t err_set = nvs_set_i64(my_handle, key, (int64_t)value);
    if (err_set != ESP_OK) {
        ESP_LOGE(TAG, "Failed to write %s to NVS!", key);
    }

    esp_err_t err_commit = nvs_commit(my_handle);
    if (err_commit != ESP_OK) {
        ESP_LOGE(TAG, "Failed to commit %s to NVS!", key);
    }
    else {
        ESP_LOGI(TAG, "Saved %s to NVS", key);
    }
    
    nvs_close(my_handle);
}

// --- Time Functions ---
void time_sync_notification_cb(struct timeval *tv) {
    ESP_LOGI(TAG, "Time synchronized");
}

static void initialize_sntp(void) {
    ESP_LOGI(TAG, "Initializing SNTP");
    esp_sntp_setoperatingmode(SNTP_OPMODE_POLL);
    esp_sntp_setservername(0, "pool.ntp.org");
sntp_set_time_sync_notification_cb(time_sync_notification_cb);
    esp_sntp_init();
}

static bool obtain_time(void) {
    initialize_sntp();
    
    setenv("TZ", TIMEZONE, 1);
    tzset();

    time_t now = 0;
    struct tm timeinfo = { 0 };
    int retry = 0;
    const int retry_count = 15;
    while (sntp_get_sync_status() == SNTP_SYNC_STATUS_RESET && ++retry < retry_count) {
        ESP_LOGI(TAG, "Waiting for system time to be set... (%d/%d)", retry, retry_count);
        vTaskDelay(2000 / portTICK_PERIOD_MS);
    }

    if (retry == retry_count) {
        ESP_LOGE(TAG, "Failed to get system time!");
        return false;
    }

    time(&now);
    localtime_r(&now, &timeinfo);
    return true;
}

// --- Tasks ---
static void vehicle_counter_task(void*) {
    while (1) {
        if (xQueueReceive(gpio_events, NULL, portMAX_DELAY)) {
            vehicle_count++;
            ESP_LOGI(TAG, "Vehicle detected. Total count: %lu", (long unsigned int)vehicle_count);
            write_u32_to_nvs("vehicle_count", vehicle_count);
        }
    }
}

static void scheduled_sender_task(void*) {
    while(1) {
        time_t now;
        time(&now);

        // Calculate the next send time
        struct tm timeinfo;
        localtime_r(&now, &timeinfo);
        timeinfo.tm_hour = SEND_HOUR;
        timeinfo.tm_min = SEND_MINUTE;
        timeinfo.tm_sec = 0;
        
        time_t next_send_time = mktime(&timeinfo);

        // If the calculated time is in the past for today, schedule for the next day
        if (now >= next_send_time) {
            next_send_time += 24 * 3600; // Add 24 hours
        }

        int64_t sleep_ms = (int64_t)difftime(next_send_time, now) * 1000;

        ESP_LOGI(TAG, "Next data send scheduled in %lld ms", sleep_ms);
        if (sleep_ms > 0) {
            vTaskDelay(pdMS_TO_TICKS(sleep_ms));
        }

        // --- Woke up, time to send ---
        ESP_LOGI(TAG, "Woke up to send data.");
        time(&now); // Update `now` to the current time for the timestamp

        if (vehicle_count > 0) {
            ESP_LOGI(TAG, "Sending data for the period. Vehicle count: %lu", (long unsigned int)vehicle_count);

            char payload[128];
            snprintf(payload, sizeof(payload), "{\"station_id\":\"%s\", \"vehicle_count\":%lu}", STATION_ID, (long unsigned int)vehicle_count);

            esp_http_client_config_t config = {
                .url = API_ENDPOINT_URL,
                .method = HTTP_METHOD_POST,
            };
            esp_http_client_handle_t client = esp_http_client_init(&config);
            esp_http_client_set_header(client, "Content-Type", "application/json");
            esp_http_client_set_post_field(client, payload, strlen(payload));

            esp_err_t err = esp_http_client_perform(client);

            if (err == ESP_OK) {
                ESP_LOGI(TAG, "HTTP POST request sent successfully, status = %d", esp_http_client_get_status_code(client));
                vehicle_count = 0; // Reset count after successful send
                write_u32_to_nvs("vehicle_count", vehicle_count);
            } else {
                ESP_LOGE(TAG, "HTTP POST request failed: %s", esp_err_to_name(err));
                // Note: If send fails, count is NOT reset, will be sent next time.
            }
            
            esp_http_client_cleanup(client);
        } else {
            ESP_LOGI(TAG, "No vehicles detected in this period, not sending data.");
        }
        
        // Record the time of this "send attempt" to mark the end of the period
        last_send_time = now;
        write_time_to_nvs("last_send_time", last_send_time);
    }
}

static void display_task(void*) {
    char time_buffer[32];
    while(1) {
        time_t now;
        time(&now);
        struct tm timeinfo;
        localtime_r(&now, &timeinfo);

        strftime(time_buffer, sizeof(time_buffer), "%Y-%m-%d %H:%M:%S", &timeinfo);
        ESP_LOGI("Clock", "Current Time: %s", time_buffer);

        struct tm next_send_tm = timeinfo;
        next_send_tm.tm_hour = SEND_HOUR;
        next_send_tm.tm_min = SEND_MINUTE;
        next_send_tm.tm_sec = 0;
        
        time_t next_send_time = mktime(&next_send_tm);

        if (now >= next_send_time) {
            next_send_time += 24 * 3600;
        }

        double remaining_seconds = difftime(next_send_time, now);
        int hours = (int)remaining_seconds / 3600;
        int minutes = ((int)remaining_seconds % 3600) / 60;
        int seconds = (int)remaining_seconds % 60;

        ESP_LOGI("Countdown", "Time until next send: %02d:%02d:%02d", hours, minutes, seconds);

        vTaskDelay(1000 / portTICK_PERIOD_MS);
    }
}

static void IRAM_ATTR gpio_isr_handler(void*) {
    uint64_t current_time = esp_timer_get_time();
    if (current_time - last_gpio_time > 1000000) {
        last_gpio_time = current_time;
        xQueueSendFromISR(gpio_events, NULL, NULL);
    }
}

static void send_reboot_ping() {
    ESP_LOGI(TAG, "Sending reboot ping...");
    char payload[128];
    snprintf(payload, sizeof(payload), "{\"station_id\":\"%s\"}", STATION_ID);
    esp_http_client_config_t config = {
        .url = "http://10.0.0.20:5000/esp32/reboot",
        .method = HTTP_METHOD_POST,
        .timeout_ms = 5000,
    };
    esp_http_client_handle_t client = esp_http_client_init(&config);
    esp_http_client_set_header(client, "Content-Type", "application/json");
    esp_http_client_set_post_field(client, payload, strlen(payload));
    esp_err_t err = esp_http_client_perform(client);
    if (err == ESP_OK) {
        ESP_LOGI(TAG, "Reboot ping sent successfully, status = %d", esp_http_client_get_status_code(client));
    } else {
        ESP_LOGE(TAG, "Reboot ping failed: %s", esp_err_to_name(err));
    }
    esp_http_client_cleanup(client);
}

void app_main(void) {
    init_nvs();
    read_u32_from_nvs("vehicle_count", &vehicle_count);
    read_time_from_nvs("last_send_time", &last_send_time);

    wifi_init_sta();
    send_reboot_ping();

    gpio_events = xQueueCreate(10, 0);
    xTaskCreate(vehicle_counter_task, "vehicle_counter_task", 4096, NULL, 10, NULL);

    if (obtain_time()) {
        xTaskCreate(scheduled_sender_task, "scheduled_sender_task", 4096, NULL, 5, NULL);
        xTaskCreate(display_task, "display_task", 4096, NULL, 4, NULL);
    } else {
        ESP_LOGE(TAG, "Failed to obtain time. Cannot start scheduled tasks.");
    }

    gpio_config_t io_config = {
        .intr_type = GPIO_INTR_POSEDGE,
        .mode = GPIO_MODE_INPUT,
        .pin_bit_mask = 1ULL << GPIO_NUM_1,
        .pull_down_en = true
    };
    gpio_config(&io_config);

    gpio_install_isr_service(0);
    gpio_isr_handler_add(GPIO_NUM_1, gpio_isr_handler, NULL);

    ESP_LOGI(TAG, "System setup complete. Waiting for events.");
}
