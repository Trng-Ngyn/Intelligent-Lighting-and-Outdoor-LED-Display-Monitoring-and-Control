/* Cấu hình dùng chung cho firmware ESP-IDF S2.
 * Mọi giá trị nhạy cảm (mật khẩu WiFi, CA/cert/key, master secret) chỉ được
 * đọc từ NVS sau khi provisioning; không giá trị nào nằm trong source/binary. */
#ifndef PCCOM_CONFIG_H
#define PCCOM_CONFIG_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/queue.h"

#define PCCOM_NVS_PARTITION "nvs"
#define PCCOM_NVS_NAMESPACE "pccom_cfg"
#define PCCOM_RUNTIME_NAMESPACE "pccom_rt"

#define PCCOM_ID_MAX 65
#define PCCOM_HOST_MAX 129
#define PCCOM_SSID_MAX 33
#define PCCOM_PASS_MAX 65
#define PCCOM_PEM_MAX 4096
#define PCCOM_SECRET_MAX 256
#define PCCOM_TOPIC_MAX 256
#define PCCOM_PAYLOAD_MAX 1024

#define PCCOM_TELEMETRY_INTERVAL_MS 10000
#define PCCOM_MQTT_KEEPALIVE_SEC 15
#define PCCOM_MQTT_QOS 1
#define PCCOM_WILL_DELAY_SEC 0

/* S3 hardening: watchdog 30s đủ cho 3 task feed; time/provisioning có timeout
 * để không bao giờ treo vĩnh viễn chờ SNTP hoặc UART. */
#define PCCOM_WDT_TIMEOUT_MS 30000
#define PCCOM_NET_WAIT_TIMEOUT_MS 120000
#define PCCOM_PROVISION_IDLE_TIMEOUT_MS 120000
#define PCCOM_PROVISION_VERSION 1u

#define PCCOM_POLL_TICK_MS 1000
#define PCCOM_WIFI_RETRY_MS 10000
#define PCCOM_SNTP_RETRY_MS 30000
#define PCCOM_STATS_LOG_MS 60000

#define PCCOM_WIFI_CONNECTED_BIT BIT0
#define PCCOM_SNTP_SYNCED_BIT BIT1
#define PCCOM_MQTT_CONNECTED_BIT BIT2

#define PCCOM_SAMPLE_QUEUE_LEN 4
#define PCCOM_PUBLISH_QUEUE_LEN 8

typedef struct {
    char site_id[PCCOM_ID_MAX];
    char device_type[PCCOM_ID_MAX];
    char device_id[PCCOM_ID_MAX];
    char client_id[PCCOM_ID_MAX];
    char broker_host[PCCOM_HOST_MAX];
    uint16_t broker_port;
    char wifi_ssid[PCCOM_SSID_MAX];
    char wifi_pass[PCCOM_PASS_MAX];

    char *ca_pem;
    size_t ca_len;
    char *cert_pem;
    size_t cert_len;
    char *key_pem;
    size_t key_len;

    /* HMAC master secret dạng bytes UTF-8; KHÔNG in ra log. */
    uint8_t *signing_secret;
    size_t signing_secret_len;
} pccom_config_t;

/* Tín hiệu nhịp 10s từ Telemetry task tới Ingestion task. */
typedef struct {
    uint8_t reserved;
} pccom_sample_request_t;

/* Một bản tin do Ingestion tạo, Network Manager là nơi duy nhất publish. */
typedef struct {
    char topic[PCCOM_TOPIC_MAX];
    char payload[PCCOM_PAYLOAD_MAX];
    char correlation_id[37];
    char ts_ms[21];
    char signature[65];
    uint8_t qos;
    uint8_t retain;
} pccom_publish_item_t;

typedef struct {
    const pccom_config_t *cfg;
    QueueHandle_t sample_queue;
    QueueHandle_t publish_queue;
    EventGroupHandle_t events;

    /* Bộ đếm vận hành để log định kỳ, không dùng cho logic nghiệp vụ. */
    volatile uint32_t dropped_samples;
    volatile uint32_t dropped_publishes;
    volatile uint32_t published;
    volatile uint32_t publish_failures;
    volatile uint32_t net_retries;
} pccom_context_t;

void pccom_config_free(pccom_config_t *cfg);
bool pccom_config_is_valid(const pccom_config_t *cfg);

#endif /* PCCOM_CONFIG_H */
