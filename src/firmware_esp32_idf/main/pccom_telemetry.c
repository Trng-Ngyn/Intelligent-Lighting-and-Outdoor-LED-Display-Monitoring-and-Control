#include "pccom_telemetry.h"

#include <inttypes.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

#include "cJSON.h"
#include "esp_log.h"
#include "esp_random.h"
#include "esp_task_wdt.h"

#include "freertos/task.h"

#include "pccom_nvs.h"
#include "pccom_security.h"

static const char *TAG = "pccom-telemetry";

static void build_topic(const pccom_config_t *cfg, const char *category, char out[PCCOM_TOPIC_MAX])
{
    snprintf(out, PCCOM_TOPIC_MAX, "%s/v1/%s/%s/%s",
             category, cfg->site_id, cfg->device_type, cfg->device_id);
}

static float jitter_tenths(uint32_t max_tenths)
{
    return (float)(esp_random() % max_tenths) / 10.0f;
}

void pccom_telemetry_task(void *arg)
{
    pccom_context_t *ctx = (pccom_context_t *)arg;
    if (ctx == NULL) {
        (void)esp_task_wdt_delete(NULL); /* tránh entry TWDT của task đã chết */
        vTaskDelete(NULL);
        return;
    }

    TickType_t wake = xTaskGetTickCount();
    for (;;) {
        vTaskDelayUntil(&wake, pdMS_TO_TICKS(PCCOM_TELEMETRY_INTERVAL_MS));
        (void)esp_task_wdt_reset();

        EventBits_t bits = xEventGroupGetBits(ctx->events);
        if ((bits & (PCCOM_SNTP_SYNCED_BIT | PCCOM_MQTT_CONNECTED_BIT)) !=
            (PCCOM_SNTP_SYNCED_BIT | PCCOM_MQTT_CONNECTED_BIT)) {
            /* Không đệm offline, không fallback: bỏ nhịp này và chờ nhịp sau. */
            ESP_LOGW(TAG, "bỏ nhịp telemetry: chưa sẵn sàng time/MQTT");
            continue;
        }

        /* Chính sách q_sample_req (len 4): không chờ, bỏ nhịp mới nhất khi
         * đầy để giữ nhịp 10s. Không đệm offline. */
        pccom_sample_request_t req = {0};
        if (xQueueSend(ctx->sample_queue, &req, 0) != pdTRUE) {
            ctx->dropped_samples++;
            ESP_LOGW(TAG, "q_sample_req đầy, bỏ nhịp lấy mẫu (dropped=%lu)",
                     (unsigned long)ctx->dropped_samples);
        }
    }
}

void pccom_ingestion_task(void *arg)
{
    pccom_context_t *ctx = (pccom_context_t *)arg;
    if (ctx == NULL) {
        (void)esp_task_wdt_delete(NULL); /* tránh entry TWDT của task đã chết */
        vTaskDelete(NULL);
        return;
    }

    const pccom_config_t *cfg = ctx->cfg;
    uint8_t device_key[32];
    if (pccom_derive_device_key(cfg, device_key) != ESP_OK) {
        ESP_LOGE(TAG, "không dẫn xuất được khóa thiết bị; ingestion dừng");
        (void)esp_task_wdt_delete(NULL); /* tránh entry TWDT của task đã chết */
        vTaskDelete(NULL);
        return;
    }

    char topic[PCCOM_TOPIC_MAX];
    build_topic(cfg, "telemetry", topic);

    pccom_sample_request_t req;
    for (;;) {
        (void)esp_task_wdt_reset();
        /* Timeout 1s thay vì portMAX_DELAY: task luôn có cơ hội feed WDT
         * ngay cả khi không có nhịp telemetry (ví dụ SNTP/MQTT chưa sẵn sàng). */
        if (xQueueReceive(ctx->sample_queue, &req, pdMS_TO_TICKS(1000)) != pdTRUE) {
            continue;
        }

        uint32_t sequence = 0;
        if (pccom_nvs_next_sequence(&sequence) != ESP_OK) {
            ESP_LOGE(TAG, "không tăng được sequence");
            continue;
        }

        char correlation_id[37];
        char ts_ms[21];
        char signature[65];
        pccom_new_uuid4(correlation_id);
        if (!pccom_epoch_ms(ts_ms)) {
            ESP_LOGE(TAG, "không lấy được epoch ms");
            continue;
        }

        float voltage = 220.0f - 2.0f + jitter_tenths(40);
        float power = 48.0f + jitter_tenths(50);
        float current = power / voltage;

        cJSON *root = cJSON_CreateObject();
        if (root == NULL) {
            ESP_LOGE(TAG, "hết nhớ khi tạo JSON");
            continue;
        }
        cJSON_AddStringToObject(root, "schema_version", "1.0.0");
        cJSON_AddStringToObject(root, "message_id", correlation_id);
        cJSON_AddStringToObject(root, "asset_id", cfg->device_id);
        cJSON_AddNumberToObject(root, "sequence", (double)sequence);
        cJSON_AddNumberToObject(root, "source_time", (double)time(NULL));

        cJSON *metrics = cJSON_AddObjectToObject(root, "metrics");
        if (metrics != NULL) {
            cJSON_AddNumberToObject(metrics, "power_w", power);
            cJSON_AddNumberToObject(metrics, "energy_wh",
                                    125.40f + (double)sequence * 0.01);
            cJSON_AddNumberToObject(metrics, "voltage_v", voltage);
            cJSON_AddNumberToObject(metrics, "current_a", current);
            cJSON_AddNumberToObject(metrics, "power_factor", 0.95);
            cJSON_AddNumberToObject(metrics, "temperature_c",
                                    47.0f - 1.0f + jitter_tenths(20));
            cJSON_AddNumberToObject(metrics, "ambient_lux",
                                    262.0f + jitter_tenths(200));
        }
        cJSON_AddNumberToObject(root, "brightness_pct", 50);
        cJSON_AddBoolToObject(root, "relay_state", cJSON_True);
        cJSON_AddStringToObject(root, "quality", "GOOD");

        char *rendered = cJSON_PrintUnformatted(root);
        cJSON_Delete(root);
        if (rendered == NULL) {
            ESP_LOGE(TAG, "không render được JSON");
            continue;
        }
        if (strlen(rendered) >= PCCOM_PAYLOAD_MAX) {
            ESP_LOGE(TAG, "payload vượt quá %d bytes", PCCOM_PAYLOAD_MAX - 1);
            cJSON_free(rendered);
            continue;
        }

        if (pccom_sign_message(device_key, topic, correlation_id, ts_ms, rendered,
                               signature) != ESP_OK) {
            cJSON_free(rendered);
            continue;
        }

        pccom_publish_item_t item;
        memset(&item, 0, sizeof(item));
        strncpy(item.topic, topic, sizeof(item.topic) - 1);
        strncpy(item.payload, rendered, sizeof(item.payload) - 1);
        strncpy(item.correlation_id, correlation_id, sizeof(item.correlation_id) - 1);
        strncpy(item.ts_ms, ts_ms, sizeof(item.ts_ms) - 1);
        strncpy(item.signature, signature, sizeof(item.signature) - 1);
        item.qos = PCCOM_MQTT_QOS;
        item.retain = 0;
        cJSON_free(rendered);

        /* Chính sách q_publish (len 8): drop-oldest, ưu tiên bản tin mới nhất.
         * Network Manager là consumer duy nhất; nếu nó vừa lấy một item trong
         * khe trống giữa receive/send thì tối đa mất thêm 1 item cũ, không
         * bao giờ block Ingestion hay làm trễ nhịp 10s. */
        if (xQueueSend(ctx->publish_queue, &item, 0) != pdTRUE) {
            pccom_publish_item_t stale;
            /* Bỏ item cũ nhất để chỗ cho seq mới nhất. */
            if (xQueueReceive(ctx->publish_queue, &stale, 0) == pdTRUE) {
                (void)xQueueSend(ctx->publish_queue, &item, 0);
            }
            ctx->dropped_publishes++;
            ESP_LOGW(TAG, "q_publish đầy, drop-oldest; giữ seq=%" PRIu32
                     " dropped=%lu", sequence,
                     (unsigned long)ctx->dropped_publishes);
        } else {
            ESP_LOGI(TAG, "đã xếp telemetry seq=%" PRIu32 " topic=%s", sequence, topic);
        }
    }
}
