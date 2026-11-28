#include "pccom_telemetry.h"

#include <inttypes.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

#define ADC_DISABLE_DEPRECATION_WARNING 1
#include "driver/adc.h"
#include "esp_log.h"
#include "esp_random.h"
#include "esp_task_wdt.h"
#include "freertos/task.h"

#include "pccom_nvs.h"
#include "pccom_security.h"

static const char *TAG = "pccom-telemetry";

/* Nguồn số liệu S4:
 * - ambient_lux: ADC1_CH6 / GPIO34 đọc thật (raw 12-bit -> mV proxy lux).
 * - power_w/energy_wh/voltage_v/current_a/power_factor/temperature_c: mô phỏng
 *   có jitter; brightness_pct/relay_state/quality là trạng thái cố định lab.
 * Tất cả được đóng gói bởi render_payload() vào buffer tĩnh: KHÔNG cấp phát
 * heap trong khi serialize (khác với cJSON_PrintUnformatted). */
#define PCCOM_ADC_CHANNEL ADC1_CHANNEL_6  /* GPIO34 */
#define PCCOM_ADC_MAX_RAW 4095.0f

static void build_topic(const pccom_config_t *cfg, const char *category, char out[PCCOM_TOPIC_MAX])
{
    snprintf(out, PCCOM_TOPIC_MAX, "%s/v1/%s/%s/%s",
             category, cfg->site_id, cfg->device_type, cfg->device_id);
}

static float jitter_tenths(uint32_t max_tenths)
{
    return (float)(esp_random() % max_tenths) / 10.0f;
}

static void init_adc(void)
{
    (void)adc1_config_width(ADC_WIDTH_BIT_12);
    (void)adc1_config_channel_atten(PCCOM_ADC_CHANNEL, ADC_ATTEN_DB_11);
}

static float read_ambient_lux(void)
{
    int raw = adc1_get_raw(PCCOM_ADC_CHANNEL);
    if (raw < 0) {
        return 0.0f;
    }
    /* Proxy tuyến tính: 0..3300mV -> 0..330 lux lab; có nghĩa là đọc ADC thật. */
    return (float)raw * 3300.0f / PCCOM_ADC_MAX_RAW / 10.0f;
}

static int render_payload(const pccom_config_t *cfg, const char *correlation_id,
                          uint32_t sequence, int64_t source_time,
                          float power, float voltage, float current,
                          float temperature, float ambient_lux,
                          char *out, size_t out_size)
{
    return snprintf(out, out_size,
                    "{\"schema_version\":\"1.0.0\",\"message_id\":\"%s\","
                    "\"asset_id\":\"%s\",\"sequence\":%" PRIu32
                    ",\"source_time\":%" PRId64 ",\"metrics\":{"
                    "\"power_w\":%.2f,\"energy_wh\":%.2f,\"voltage_v\":%.2f,"
                    "\"current_a\":%.3f,\"power_factor\":0.95,"
                    "\"temperature_c\":%.2f,\"ambient_lux\":%.1f},"
                    "\"brightness_pct\":50,\"relay_state\":true,"
                    "\"quality\":\"GOOD\"}",
                    correlation_id, cfg->device_id, sequence, source_time,
                    power, 125.40 + (double)sequence * 0.01, voltage, current,
                    temperature, ambient_lux);
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
        /* Chỉ task này có vTaskDelayUntil 10s; 2 task kia chạy theo event/queue. */
        vTaskDelayUntil(&wake, pdMS_TO_TICKS(PCCOM_TELEMETRY_INTERVAL_MS));
        (void)esp_task_wdt_reset();

        EventBits_t bits = xEventGroupGetBits(ctx->events);
        if ((bits & (PCCOM_SNTP_SYNCED_BIT | PCCOM_MQTT_CONNECTED_BIT)) !=
            (PCCOM_SNTP_SYNCED_BIT | PCCOM_MQTT_CONNECTED_BIT)) {
            /* Không đệm offline, không fallback: bỏ nhịp này và chờ nhịp sau. */
            ESP_LOGW(TAG, "bỏ nhịp telemetry: chưa sẵn sàng time/MQTT");
            continue;
        }

        pccom_sample_request_t req = {0};
        if (xQueueSend(ctx->sample_queue, &req, 0) != pdTRUE) {
            ctx->dropped_samples++;
            ctx->queue_overflow++;
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
    if (pccom_copy_device_key(cfg, device_key) != ESP_OK) {
        ESP_LOGE(TAG, "không đọc được device key; ingestion dừng");
        (void)esp_task_wdt_delete(NULL); /* tránh entry TWDT của task đã chết */
        vTaskDelete(NULL);
        return;
    }

    init_adc();
    char topic[PCCOM_TOPIC_MAX];
    build_topic(cfg, "telemetry", topic);

    pccom_sample_request_t req;
    for (;;) {
        (void)esp_task_wdt_reset();
        /* Ingestion chỉ chạy khi có q_sample_req từ nhịp 10s của Telemetry. */
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
            /* SNTP đã sync ở bước trước nên ts_ms/source_time là epoch thật. */
            ESP_LOGE(TAG, "không lấy được epoch ms");
            continue;
        }

        float voltage = 220.0f - 2.0f + jitter_tenths(40);
        float power = 48.0f + jitter_tenths(50);
        float current = power / voltage;
        float temperature = 47.0f - 1.0f + jitter_tenths(20);
        float ambient_lux = read_ambient_lux();

        char rendered[PCCOM_PAYLOAD_MAX];
        int written = render_payload(cfg, correlation_id, sequence,
                                     (int64_t)time(NULL), power, voltage, current,
                                     temperature, ambient_lux,
                                     rendered, sizeof(rendered));
        if (written < 0 || (size_t)written >= sizeof(rendered)) {
            ESP_LOGE(TAG, "payload vượt quá %d bytes", PCCOM_PAYLOAD_MAX - 1);
            continue;
        }

        if (pccom_sign_message(device_key, topic, correlation_id, ts_ms, rendered,
                               signature) != ESP_OK) {
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

        /* Chính sách q_publish (len 8): drop-oldest, ưu tiên bản tin mới nhất.
         * Network Manager là consumer duy nhất; không chờ/block ingestion. */
        if (xQueueSend(ctx->publish_queue, &item, 0) != pdTRUE) {
            pccom_publish_item_t stale;
            if (xQueueReceive(ctx->publish_queue, &stale, 0) == pdTRUE) {
                (void)xQueueSend(ctx->publish_queue, &item, 0);
            }
            ctx->dropped_publishes++;
            ctx->queue_overflow++;
            ESP_LOGW(TAG, "q_publish đầy, drop-oldest; giữ seq=%" PRIu32
                     " dropped=%lu", sequence,
                     (unsigned long)ctx->dropped_publishes);
        } else {
            ESP_LOGI(TAG, "đã xếp telemetry seq=%" PRIu32 " topic=%s", sequence, topic);
        }
    }
}
