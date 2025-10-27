#include <string.h>
#include <inttypes.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "esp_event.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "nvs.h"
#include "esp_http_client.h"
#include "driver/gpio.h"
#include "esp_timer.h" // Include for esp_timer_get_time()
#include "wifi.h"

#define TAG "main"

// --- Configuration ---
#define API_ENDPOINT_URL "http://10.0.0.20:5000/record_vehicle_event"
#define STATION_ID "68e9b597390df31a18fcafea" // Example ID - CHANGE THIS
#define STORAGE_NAMESPACE "storage"
#define COUNTDOWN_SECONDS 60
// ---------------------

static QueueHandle_t gpio_events = NULL;
static uint32_t vehicle_count = 0;
static uint32_t countdown_val = COUNTDOWN_SECONDS;
static uint64_t last_gpio_time = 0; // To store the timestamp of the last processed GPIO event

// --- NVS Functions ---
void init_nvs() {
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);
}

void read_vehicle_count_from_nvs() {
    nvs_handle_t my_handle;
    esp_err_t err = nvs_open(STORAGE_NAMESPACE, NVS_READWRITE, &my_handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Error opening NVS handle!");
        return;
    }

    err = nvs_get_u32(my_handle, "vehicle_count", &vehicle_count);
    switch (err) {
        case ESP_OK:
            ESP_LOGI(TAG, "Successfully read vehicle count from NVS: %lu", (long unsigned int)vehicle_count);
            break;
        case ESP_ERR_NVS_NOT_FOUND:
            ESP_LOGI(TAG, "Vehicle count not found in NVS, initializing to 0");
            vehicle_count = 0;
            break;
        default:
            ESP_LOGE(TAG, "Error reading vehicle count from NVS!");
    }
    nvs_close(my_handle);
}

void write_vehicle_count_to_nvs() {
    nvs_handle_t my_handle;
    esp_err_t err = nvs_open(STORAGE_NAMESPACE, NVS_READWRITE, &my_handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Error opening NVS handle!");
        return;
    }

    err = nvs_set_u32(my_handle, "vehicle_count", vehicle_count);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to write vehicle count to NVS!");
    }

    err = nvs_commit(my_handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to commit vehicle count to NVS!");
    } else {
        ESP_LOGI(TAG, "Saved vehicle count to NVS: %lu", (long unsigned int)vehicle_count);
    }
    
    nvs_close(my_handle);
}

void read_countdown_from_nvs() {
    nvs_handle_t my_handle;
    esp_err_t err = nvs_open(STORAGE_NAMESPACE, NVS_READWRITE, &my_handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Error opening NVS handle for countdown!");
        return;
    }

    err = nvs_get_u32(my_handle, "countdown_val", &countdown_val);
    switch (err) {
        case ESP_OK:
            ESP_LOGI(TAG, "Successfully read countdown value from NVS: %lu", (long unsigned int)countdown_val);
            break;
        case ESP_ERR_NVS_NOT_FOUND:
            ESP_LOGI(TAG, "Countdown value not found in NVS, initializing to %d", COUNTDOWN_SECONDS);
            countdown_val = COUNTDOWN_SECONDS;
            break;
        default:
            ESP_LOGE(TAG, "Error reading countdown value from NVS!");
            countdown_val = COUNTDOWN_SECONDS;
    }
    nvs_close(my_handle);
}

void write_countdown_to_nvs() {
    nvs_handle_t my_handle;
    esp_err_t err = nvs_open(STORAGE_NAMESPACE, NVS_READWRITE, &my_handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Error opening NVS handle for countdown!");
        return;
    }

    err = nvs_set_u32(my_handle, "countdown_val", countdown_val);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to write countdown value to NVS!");
    }

    err = nvs_commit(my_handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to commit countdown value to NVS!");
    }
    
    nvs_close(my_handle);
}
// --------------------

static void vehicle_counter_task(void*)
{
    while (1) {
        // Wait forever for a GPIO event
        if (xQueueReceive(gpio_events, NULL, portMAX_DELAY)) {
            vehicle_count++;
            ESP_LOGI(TAG, "Vehicle detected. Total count: %lu", (long unsigned int)vehicle_count);
            write_vehicle_count_to_nvs();
        }
    }
}

static void weekly_sender_task(void*)
{
    while(1) {
        if (countdown_val == 0 || countdown_val > COUNTDOWN_SECONDS) {
            countdown_val = COUNTDOWN_SECONDS;
        }

        for (int i = countdown_val; i > 0; i--) {
            ESP_LOGI(TAG, "Countdown: %d seconds remaining...", i);
            vTaskDelay(1000 / portTICK_PERIOD_MS);
            countdown_val = i - 1;
            write_countdown_to_nvs();
        }

        if (vehicle_count > 0) {
            ESP_LOGI(TAG, "Timer elapsed. Sending data...");

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
                vehicle_count = 0;
                write_vehicle_count_to_nvs();
                countdown_val = COUNTDOWN_SECONDS; // Reset timer for next cycle
                write_countdown_to_nvs();
            } else {
                ESP_LOGE(TAG, "HTTP POST request failed: %s", esp_err_to_name(err));
            }
            
            esp_http_client_cleanup(client);
        } else {
            ESP_LOGI(TAG, "Timer elapsed. No vehicles detected, not sending data.");
            countdown_val = COUNTDOWN_SECONDS; // Reset timer for next cycle
            write_countdown_to_nvs();
        }
    }
}


static void IRAM_ATTR gpio_isr_handler(void*) {
    uint64_t current_time = esp_timer_get_time();
    if (current_time - last_gpio_time > 1000000) { // 1 second in microseconds
        last_gpio_time = current_time;
        xQueueSendFromISR(gpio_events, NULL, NULL);
    }
}

static void send_reboot_ping() {
    ESP_LOGI(TAG, "Sending reboot ping...");

    char payload[128];
    snprintf(payload, sizeof(payload), "{\"station_id\":\"%s\"}", STATION_ID);

    esp_http_client_config_t config = {
        .url = "http://10.0.0.20:5000/esp32/reboot", // New endpoint for reboot pings
        .method = HTTP_METHOD_POST,
        .timeout_ms = 5000, // 5 second timeout
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

void app_main(void)
{
    // Initialize NVS
    init_nvs();
    read_vehicle_count_from_nvs();
    read_countdown_from_nvs();

    // Initialize WiFi
    wifi_init_sta();

    // Send reboot ping after WiFi is connected
    send_reboot_ping();

    // Create the queue and tasks
    gpio_events = xQueueCreate(10, 0);
    xTaskCreate(vehicle_counter_task, "vehicle_counter_task", 2048, NULL, 10, NULL);
    xTaskCreate(weekly_sender_task, "weekly_sender_task", 4096, NULL, 5, NULL);


    // Configure the GPIO pin
    gpio_config_t io_config = {
        .intr_type = GPIO_INTR_POSEDGE,
        .mode = GPIO_MODE_INPUT,
        .pin_bit_mask = 1ULL << GPIO_NUM_1, // need to chnages this back to GPIO_NUM_1 for the wifi esp32
        .pull_down_en = true
    };
    gpio_config(&io_config);

    // Install ISR service and add handler
    gpio_install_isr_service(0);
    gpio_isr_handler_add(GPIO_NUM_1, gpio_isr_handler, NULL);

    ESP_LOGI(TAG, "System setup complete. Waiting for events.");
}