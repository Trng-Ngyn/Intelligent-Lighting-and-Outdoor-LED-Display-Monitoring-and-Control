/* PCCOM ESP32-WROOM-32 firmware (S2+S3): telemetry Annex C + MQTT 5/mTLS +
 * HMAC + hardening. Có đúng 3 task ứng dụng: Network Manager, Ingestion,
 * Telemetry. */
#include <stdio.h>

#include "esp_log.h"
#include "esp_system.h"
#include "esp_task_wdt.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/queue.h"
#include "freertos/task.h"

#include "pccom_config.h"
#include "pccom_network.h"
#include "pccom_nvs.h"
#include "pccom_provision.h"
#include "pccom_security.h"
#include "pccom_telemetry.h"

#if defined(PCCOM_PROFILE_DEV)
#define PCCOM_PROFILE_NAME "dev"
#elif defined(PCCOM_PROFILE_SECURE)
#define PCCOM_PROFILE_NAME "secure"
#else
#define PCCOM_PROFILE_NAME "unknown"
#endif

static const char *TAG = "pccom-main";

void app_main(void)
{
    ESP_LOGI(TAG, "PCCOM ESP32-WROOM-32 firmware ready");
    ESP_LOGI(TAG, "profile=%s idf=%s", PCCOM_PROFILE_NAME, esp_get_idf_version());

    if (!pccom_security_selftest()) {
        ESP_LOGE(TAG, "HMAC self-test thất bại so với vector Python; dừng boot");
        return;
    }
    ESP_LOGI(TAG, "HMAC self-test OK (vector Python)");

    esp_err_t err = pccom_nvs_init();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "NVS init failed: %s", esp_err_to_name(err));
        return;
    }

    static pccom_config_t cfg;
    while (!pccom_nvs_has_config()) {
        ESP_LOGW(TAG, "chưa có cấu hình trong NVS; chờ provisioning UART1");
        err = pccom_provision_wait(&cfg);
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "provisioning failed: %s; thử lại sau 3s",
                     esp_err_to_name(err));
            vTaskDelay(pdMS_TO_TICKS(3000));
        }
    }

    err = pccom_nvs_load(&cfg);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "đọc cấu hình failed: %s", esp_err_to_name(err));
        return;
    }

    static pccom_context_t ctx;
    ctx.cfg = &cfg;
    ctx.events = xEventGroupCreate();
    ctx.sample_queue = xQueueCreate(PCCOM_SAMPLE_QUEUE_LEN,
                                    sizeof(pccom_sample_request_t));
    ctx.publish_queue = xQueueCreate(PCCOM_PUBLISH_QUEUE_LEN,
                                     sizeof(pccom_publish_item_t));
    if (ctx.events == NULL || ctx.sample_queue == NULL || ctx.publish_queue == NULL) {
        ESP_LOGE(TAG, "không tạo được queue/event group");
        return;
    }

    /* S3: sdkconfig bật TWDT sẵn với timeout 5s và giám sát idle task CPU0/1.
     * Reconfigure sang 30s, bỏ idle task (không phải task ứng dụng) rồi đăng ký
     * đúng 3 task của firmware. Provisioning chạy trước đó nên không cần feed. */
    const esp_task_wdt_config_t wdt_cfg = {
        .timeout_ms = PCCOM_WDT_TIMEOUT_MS,
        .idle_core_mask = 0,
        .trigger_panic = true,
    };
    err = esp_task_wdt_reconfigure(&wdt_cfg);
    if (err == ESP_ERR_INVALID_STATE) {
        err = esp_task_wdt_init(&wdt_cfg);
    }
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "không cấu hình được TWDT: %s", esp_err_to_name(err));
        return;
    }

    TaskHandle_t net_task = NULL;
    TaskHandle_t ingest_task = NULL;
    TaskHandle_t tele_task = NULL;

    BaseType_t ok = xTaskCreate(&pccom_network_task, "pccom-net", 8192, &ctx, 5,
                                &net_task);
    if (ok != pdPASS || esp_task_wdt_add(net_task) != ESP_OK) {
        ESP_LOGE(TAG, "không tạo/đăng ký được Network Manager task");
        return;
    }
    ok = xTaskCreate(&pccom_ingestion_task, "pccom-ingest", 6144, &ctx, 5,
                     &ingest_task);
    if (ok != pdPASS || esp_task_wdt_add(ingest_task) != ESP_OK) {
        ESP_LOGE(TAG, "không tạo/đăng ký được Ingestion task");
        return;
    }
    ok = xTaskCreate(&pccom_telemetry_task, "pccom-tele", 4096, &ctx, 5,
                     &tele_task);
    if (ok != pdPASS || esp_task_wdt_add(tele_task) != ESP_OK) {
        ESP_LOGE(TAG, "không tạo/đăng ký được Telemetry task");
        return;
    }

    ESP_LOGI(TAG, "3 task ứng dụng đã khởi động (net/ingest/tele), TWDT %lums",
             (unsigned long)PCCOM_WDT_TIMEOUT_MS);
    vTaskDelete(NULL);
}
