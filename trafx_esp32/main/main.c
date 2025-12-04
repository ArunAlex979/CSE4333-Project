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
#include "esp_crt_bundle.h"
#include "driver/gpio.h"
#include "esp_timer.h"
#include "esp_sntp.h"
#include "sim7600.h"
#include "esp_system.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"

#define TAG "main"
#define STORAGE_NAMESPACE "storage"

// From the LilyGo example, the battery ADC pin is 35 for the T-SIM7600.
// GPIO35 is ADC1_CHANNEL_7.
#define BATT_ADC_PIN ADC_CHANNEL_7
#define BATT_MAX_VOLTAGE_MV 4200 // Max voltage for a 1S LiPo battery (4.2V)
#define BATT_MIN_VOLTAGE_MV 3000 // Min voltage for a 1S LiPo battery (3.0V)

// --- Configuration ---
#define API_ENDPOINT_URL "https://trafxcloud.uc.r.appspot.com/api/record_vehicle_event"
#define REBOOT_ENDPOINT_URL "https://trafxcloud.uc.r.appspot.com/api/esp32/reboot"
#define STATION_ID "J7PrtYPaRs9yL9xatx9p" // Example ID - CHANGE THIS
#define TIMEZONE "CST6CDT,M3.2.0,M11.1.0"
// --------------------

static QueueHandle_t gpio_events = NULL;
static uint32_t vehicle_count = 0;
static uint64_t last_gpio_time = 0;
static volatile uint32_t battery_voltage = 0;
static bool low_battery_warning_sent = false;

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

// --- Battery Functions ---
static uint8_t calculate_battery_percentage(uint32_t voltage_mv) {
    if (voltage_mv >= BATT_MAX_VOLTAGE_MV) {
        return 100;
    }
    if (voltage_mv <= BATT_MIN_VOLTAGE_MV) {
        return 0;
    }
    // Linear interpolation
    uint32_t range = BATT_MAX_VOLTAGE_MV - BATT_MIN_VOLTAGE_MV;
    uint32_t voltage_above_min = voltage_mv - BATT_MIN_VOLTAGE_MV;
    return (uint8_t)((voltage_above_min * 100) / range);
}

static adc_oneshot_unit_handle_t adc1_handle;
static adc_cali_handle_t cali_handle = NULL;

static void init_battery_reader(void) {
    //-------------ADC1 Init---------------//
    adc_oneshot_unit_init_cfg_t init_config1 = {
        .unit_id = ADC_UNIT_1,
    };
    ESP_ERROR_CHECK(adc_oneshot_new_unit(&init_config1, &adc1_handle));

    //-------------ADC1 Config---------------//
    adc_oneshot_chan_cfg_t config = {
        .bitwidth = ADC_BITWIDTH_DEFAULT,
        .atten = ADC_ATTEN_DB_12,
    };
    ESP_ERROR_CHECK(adc_oneshot_config_channel(adc1_handle, BATT_ADC_PIN, &config));

    //-------------ADC1 Calibration Init---------------//
    adc_cali_line_fitting_config_t cali_config = {
        .unit_id = ADC_UNIT_1,
        .atten = ADC_ATTEN_DB_12,
        .bitwidth = ADC_BITWIDTH_DEFAULT,
    };
    esp_err_t ret = adc_cali_create_scheme_line_fitting(&cali_config, &cali_handle);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "ADC Calibration failed.");
    }
}

static uint32_t read_battery_voltage(void) {
    int adc_raw;
    int voltage = 0;

    // Multisampling for better accuracy
    uint64_t adc_sum = 0;
    for (int i = 0; i < 64; i++) {
        ESP_ERROR_CHECK(adc_oneshot_read(adc1_handle, BATT_ADC_PIN, &adc_raw));
        adc_sum += adc_raw;
    }
    adc_raw = adc_sum / 64;

    if (cali_handle) {
        ESP_ERROR_CHECK(adc_cali_raw_to_voltage(cali_handle, adc_raw, &voltage));
    } else {
        // Fallback to raw value if calibration failed
        voltage = adc_raw;
    }

    // The hardware uses a voltage divider, so multiply by 2 to get the actual voltage.
    voltage *= 2;
    return (uint32_t)voltage;
}

static void battery_reader_task(void *pvParameters) {
    while (1) {
        uint32_t voltage = read_battery_voltage();
        battery_voltage = voltage; // Store the voltage globally
        uint8_t percentage = calculate_battery_percentage(voltage);
        ESP_LOGI("Battery", "Voltage: %d mV, Percentage: %d%%", voltage, percentage);

        if (percentage < 10 && !low_battery_warning_sent) {
            ESP_LOGW(TAG, "Battery level is low (%d%%), would send warning if configured.", percentage);
            // Here you could implement an HTTP call for low battery warning if needed
            // For now, just log it and set the flag.
            low_battery_warning_sent = true;
        } else if (percentage >= 15) {
            // Reset the flag if the battery has recharged to a safe level
            low_battery_warning_sent = false;
        }

        // Wait for a while before the next reading
        vTaskDelay(pdMS_TO_TICKS(30000)); // Read every 30 seconds
    }
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

static void send_data_task(void*) {
    while(1) {
        for (int i = 5; i > 0; i--) {
            printf("Sending data in %d seconds...\n", i);
            vTaskDelay(1000 / portTICK_PERIOD_MS);
        }

        time_t now;
        time(&now);

        if (vehicle_count > 0) {
            ESP_LOGI(TAG, "Sending data. Vehicle count: %lu", (long unsigned int)vehicle_count);
            
            uint32_t current_battery_voltage = read_battery_voltage();
            uint8_t current_battery_percentage = calculate_battery_percentage(current_battery_voltage);

            char payload[512]; 
            snprintf(payload, sizeof(payload), 
                "{\"station_id\":\"%s\", \"vehicle_count\":%lu, \"timestamp\":%lld, \"battery_voltage\":%lu, \"battery_percentage\":%u, \"battery_level\":%u}", 
                STATION_ID, (long unsigned int)vehicle_count, (long long)now, (long unsigned int)current_battery_voltage, current_battery_percentage, current_battery_percentage);

            esp_http_client_config_t config = {
                .url = API_ENDPOINT_URL,
                .method = HTTP_METHOD_POST,
                .crt_bundle_attach = esp_crt_bundle_attach,
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
            }
            
            esp_http_client_cleanup(client);
        } else {
            ESP_LOGI(TAG, "No vehicles detected in this period, not sending data.");
        }
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
    time_t now;
    time(&now);
    
    uint32_t current_battery_voltage = read_battery_voltage();
    uint8_t current_battery_percentage = calculate_battery_percentage(current_battery_voltage);

    char payload[512];
    snprintf(payload, sizeof(payload), 
        "{\"station_id\":\"%s\", \"event\":\"reboot\", \"timestamp\":%lld, \"vehicle_count\":%lu, \"battery_voltage\":%lu, \"battery_percentage\":%u}", 
        STATION_ID, (long long)now, (long unsigned int)vehicle_count, (long unsigned int)current_battery_voltage, current_battery_percentage);

    esp_http_client_config_t config = {
        .url = REBOOT_ENDPOINT_URL,
        .method = HTTP_METHOD_POST,
        .timeout_ms = 5000,
        .crt_bundle_attach = esp_crt_bundle_attach,
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
    init_battery_reader();
    init_nvs();
    read_u32_from_nvs("vehicle_count", &vehicle_count);

    // Start vehicle counting immediately
    gpio_events = xQueueCreate(10, 0);
    xTaskCreate(vehicle_counter_task, "vehicle_counter_task", 4096, NULL, 10, NULL);

    gpio_config_t io_config = {
        .intr_type = GPIO_INTR_POSEDGE,
        .mode = GPIO_MODE_INPUT,
        .pin_bit_mask = 1ULL << GPIO_NUM_13,
        .pull_down_en = true
    };
    gpio_config(&io_config);

    gpio_install_isr_service(0);
    gpio_isr_handler_add(GPIO_NUM_13, gpio_isr_handler, NULL);

    ESP_LOGI(TAG, "Vehicle counting started. Initializing cellular connection and time sync.");

    sim7600_init();

    // Loop until time is obtained
    while (!obtain_time()) {
        ESP_LOGE(TAG, "Failed to obtain time. Retrying in 60 seconds...");
        vTaskDelay(60000 / portTICK_PERIOD_MS);
    }

    // Time is synced, send reboot ping
    send_reboot_ping();

    // Start scheduled tasks
    xTaskCreate(send_data_task, "send_data_task", 8192, NULL, 5, NULL);
    xTaskCreate(battery_reader_task, "battery_reader_task", 8192, NULL, 5, NULL);

    ESP_LOGI(TAG, "System setup complete. Waiting for events.");
}
