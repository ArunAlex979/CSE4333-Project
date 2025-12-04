#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_netif_defaults.h"
#include "esp_netif_ppp.h"
#include "esp_modem_api.h"
#include "esp_modem_dce_config.h"
#include "esp_log.h"
#include "driver/gpio.h"
#include "sim7600.h"

#define TAG "sim7600"

// Pin definitions from the .ino file
#define MODEM_PWRKEY 4
#define MODEM_DTR 25
#define MODEM_TX 27
#define MODEM_RX 26
#define MODEM_RI 33
#define MODEM_FLIGHT 25 // Note: Same as DTR in .ino, might need adjustment. Using DTR pin.

static EventGroupHandle_t event_group = NULL;
static const int CONNECT_BIT = BIT0;

static void on_ip_event(void *arg, esp_event_base_t event_base,
                      int32_t event_id, void *event_data)
{
    ESP_LOGI(TAG, "IP event! %" PRId32, event_id);
    if (event_id == IP_EVENT_PPP_GOT_IP) {
        esp_netif_dns_info_t dns_info;

        ip_event_got_ip_t *event = (ip_event_got_ip_t *)event_data;
        esp_netif_t *netif = event->esp_netif;

        ESP_LOGI(TAG, "Modem Connected to PPP Server");
        ESP_LOGI(TAG, "~~~~~~~~~~~~~~");
        ESP_LOGI(TAG, "IP          : " IPSTR, IP2STR(&event->ip_info.ip));
        ESP_LOGI(TAG, "Netmask     : " IPSTR, IP2STR(&event->ip_info.netmask));
        ESP_LOGI(TAG, "Gateway     : " IPSTR, IP2STR(&event->ip_info.gw));
        esp_netif_get_dns_info(netif, ESP_NETIF_DNS_MAIN, &dns_info);
        ESP_LOGI(TAG, "Main DNS    : " IPSTR, IP2STR(&dns_info.ip.u_addr.ip4));
        esp_netif_get_dns_info(netif, ESP_NETIF_DNS_BACKUP, &dns_info);
        ESP_LOGI(TAG, "Backup DNS  : " IPSTR, IP2STR(&dns_info.ip.u_addr.ip4));
        ESP_LOGI(TAG, "~~~~~~~~~~~~~~");
        xEventGroupSetBits(event_group, CONNECT_BIT);
    } else if (event_id == IP_EVENT_PPP_LOST_IP) {
        ESP_LOGI(TAG, "Modem Lost IP");
    }
}

void sim7600_init(void)
{
    event_group = xEventGroupCreate();

    // Initialize the underlying TCP/IP stack
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, ESP_EVENT_ANY_ID, &on_ip_event, NULL));

    // Create netif object
    esp_netif_config_t cfg = ESP_NETIF_DEFAULT_PPP();
    esp_netif_t *esp_netif = esp_netif_new(&cfg);
    assert(esp_netif);

    /* Power on the modem */
    gpio_set_direction(MODEM_PWRKEY, GPIO_MODE_OUTPUT);
    gpio_set_level(MODEM_PWRKEY, 0);
    vTaskDelay(pdMS_TO_TICKS(100));
    gpio_set_level(MODEM_PWRKEY, 1);
    vTaskDelay(pdMS_TO_TICKS(1000));
    gpio_set_level(MODEM_PWRKEY, 0);

    // Wait for the modem to power on
    vTaskDelay(pdMS_TO_TICKS(5000));

    /* Configure the modem */
    esp_modem_dte_config_t dte_config = ESP_MODEM_DTE_DEFAULT_CONFIG();
    dte_config.uart_config.tx_io_num = MODEM_TX;
    dte_config.uart_config.rx_io_num = MODEM_RX;
    dte_config.uart_config.baud_rate = 115200;
    
    esp_modem_dce_config_t dce_config = ESP_MODEM_DCE_DEFAULT_CONFIG(CONFIG_TRAFX_MODEM_APN);
    
    ESP_LOGI(TAG, "Initializing esp_modem for the SIM7600 module...");

    esp_modem_dce_t *dce = esp_modem_new_dev(ESP_MODEM_DCE_SIM7600, &dte_config, &dce_config, esp_netif);
    assert(dce);

    int rssi, ber;
    int retries = 0;
    while(retries < 20) {
        if (esp_modem_get_signal_quality(dce, &rssi, &ber) == ESP_OK) {
            ESP_LOGI(TAG, "Signal quality: rssi=%d, ber=%d", rssi, ber);
            if (rssi > 0 && rssi != 99) {
                ESP_LOGI(TAG, "Got signal quality, proceeding.");
                break;
            }
        }
        vTaskDelay(pdMS_TO_TICKS(1000));
        retries++;
    }

    ESP_ERROR_CHECK(esp_modem_set_mode(dce, ESP_MODEM_MODE_DATA));

    /* Wait for IP address */
    ESP_LOGI(TAG, "Waiting for IP address");
    xEventGroupWaitBits(event_group, CONNECT_BIT, pdFALSE, pdFALSE, portMAX_DELAY);
    ESP_LOGI(TAG, "Modem setup complete.");
}