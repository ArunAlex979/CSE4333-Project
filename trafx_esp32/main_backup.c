#include <string.h>
#include <sys/unistd.h>
#include <sys/stat.h>
#include "esp_err.h"
#include "esp_log.h"
#include "esp_spiffs.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "esp_event.h"
#include "nvs_flash.h"
#include "esp_http_client.h"
#include "esp_tls.h"
#include "driver/gpio.h"
#include "freertos/queue.h"
#include "wifi.h"

#define TAG "main"

// --- Configuration ---
// IMPORTANT: Replace with your actual IP and a valid Station ID from your database
#define LOCAL_API_URL_UPDATE "http://10.0.0.20:5000/update_vehicle_count"
#define LOCAL_API_URL_BATCH "http://10.0.0.20:5000/update_batch"
#define STATION_ID "687fd63ff454a96ef4fe3722" // Example ID
// ---------------------

#define OFFLINE_CACHE_FILE "/spiffs/offline.txt"

static QueueHandle_t gpio_events = NULL;

// --- SPIFFS Helper Functions ---

static void init_spiffs(void)
{
    ESP_LOGI(TAG, "Initializing SPIFFS");
    esp_vfs_spiffs_conf_t conf = {
      .base_path = "/spiffs",
      .partition_label = "storage", // Must match partitions.csv
      .max_files = 5,
      .format_if_mount_failed = true
    };

    esp_err_t ret = esp_vfs_spiffs_register(&conf);

    if (ret != ESP_OK) {
        if (ret == ESP_FAIL) {
            ESP_LOGE(TAG, "Failed to mount or format filesystem");
        } else if (ret == ESP_ERR_NOT_FOUND) {
            ESP_LOGE(TAG, "Failed to find SPIFFS partition. Did you flash with partitions.csv?");
        } else {
            ESP_LOGE(TAG, "Failed to initialize SPIFFS (%s)", esp_err_to_name(ret));
        }
        return;
    }
}

int read_offline_count()
{
    FILE* f = fopen(OFFLINE_CACHE_FILE, "r");
    if (f == NULL) {
        return 0; // File doesn't exist, so count is 0
    }
    int count = 0;
    fscanf(f, "%d", &count);
    fclose(f);
    return count;
}

void write_offline_count(int count)
{
    FILE* f = fopen(OFFLINE_CACHE_FILE, "w");
    if (f == NULL) {
        ESP_LOGE(TAG, "Failed to open offline cache for writing.");
        return;
    }
    fprintf(f, "%d", count);
    fclose(f);
}

void clear_offline_cache()
{
    // Check if file exists before trying to delete
    struct stat st;
    if (stat(OFFLINE_CACHE_FILE, &st) == 0) {
        unlink(OFFLINE_CACHE_FILE);
        ESP_LOGI(TAG, "Offline cache cleared.");
    }
}

// --- HTTP Task ---

// Returns true if sync was successful or not needed, false if it failed.
bool sync_offline_cache()
{
    int offline_count = read_offline_count();
    if (offline_count <= 0) {
        return true; // Nothing to sync
    }

    ESP_LOGI(TAG, "Offline cache has %d events. Attempting to sync.", offline_count);

    char payload[128];
    snprintf(payload, sizeof(payload), "{\"station_id\":\"%s\", \"count\":%d}", STATION_ID, offline_count);

    esp_http_client_config_t config = {
        .url = LOCAL_API_URL_BATCH,
        .method = HTTP_METHOD_POST,
    };
    esp_http_client_handle_t client = esp_http_client_init(&config);
    esp_http_client_set_header(client, "Content-Type", "application/json");
    esp_http_client_set_post_field(client, payload, strlen(payload));

    esp_err_t err = esp_http_client_perform(client);
    bool success = false;
    if (err == ESP_OK && esp_http_client_get_status_code(client) == 200) {
        ESP_LOGI(TAG, "Successfully synced %d offline events.", offline_count);
        clear_offline_cache();
        success = true;
    } else {
        ESP_LOGE(TAG, "Failed to sync offline events. Will retry on next event. Error: %s", esp_err_to_name(err));
        success = false;
    }
    esp_http_client_cleanup(client);
    return success;
}

static void gpio_task(void*)
{
    while (1) {
        if (xQueueReceive(gpio_events, NULL, portMAX_DELAY)) {
            ESP_LOGI(TAG, "GPIO event received.");

            // 1. Sync offline data. If sync fails, stop and wait for next event.
            bool sync_ok = sync_offline_cache();
            if (!sync_ok) {
                continue; // Don't process live event if sync failed, to preserve order.
            }

            // 2. Attempt to send the current event
            char payload[128];
            snprintf(payload, sizeof(payload), "{\"station_id\":\"%s\"}", STATION_ID);

            esp_http_client_config_t config = {
                .url = LOCAL_API_URL_UPDATE,
                .method = HTTP_METHOD_POST,
            };
            esp_http_client_handle_t client = esp_http_client_init(&config);
            esp_http_client_set_header(client, "Content-Type", "application/json");
            esp_http_client_set_post_field(client, payload, strlen(payload));

            esp_err_t err = esp_http_client_perform(client);
            if (err == ESP_OK && esp_http_client_get_status_code(client) == 200) {
                ESP_LOGI(TAG, "Successfully sent live event.");
            } else {
                ESP_LOGE(TAG, "Failed to send live event, caching. Error: %s", esp_err_to_name(err));
                // 3. If it fails, cache it
                int current_offline_count = read_offline_count();
                write_offline_count(current_offline_count + 1);
                ESP_LOGI(TAG, "Offline count is now %d", current_offline_count + 1);
            }
            esp_http_client_cleanup(client);
        }
    }
}

// --- Main ---

static void IRAM_ATTR gpio_isr_handler(void*) {
    xQueueSendFromISR(gpio_events, NULL, NULL);
}

void app_main(void)
{
    //Initialize NVS
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
      ESP_ERROR_CHECK(nvs_flash_erase());
      ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    wifi_init_sta();
    init_spiffs();

    gpio_events = xQueueCreate(10, 0);
    xTaskCreate(gpio_task, "gpio_task", 4096, NULL, 10, NULL);

    gpio_config_t io_config = {
        .intr_type = GPIO_INTR_POSEDGE,
        .mode = GPIO_MODE_INPUT,
        .pin_bit_mask = 1 << GPIO_NUM_1,
        .pull_down_en = true
    };
    gpio_config(&io_config);

    gpio_install_isr_service(0);
    gpio_isr_handler_add(GPIO_NUM_1, gpio_isr_handler, NULL);

    ESP_LOGI(TAG, "System setup complete. Waiting for events.");

    vTaskDelay(portMAX_DELAY);
}