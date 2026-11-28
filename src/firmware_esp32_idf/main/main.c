/* PCCOM firmware scaffold (S1). Chỉ kiểm chứng toolchain ESP-IDF/MQTT 5/TLS 1.3.
 * Telemetry, HMAC và 3 task FreeRTOS được thêm ở S2. */
#include <stdio.h>

#include "esp_log.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#if defined(PCCOM_PROFILE_DEV)
#define PCCOM_PROFILE_NAME "dev"
#elif defined(PCCOM_PROFILE_SECURE)
#define PCCOM_PROFILE_NAME "secure"
#else
#define PCCOM_PROFILE_NAME "unknown"
#endif

static const char *TAG = "pccom-scaffold";

void app_main(void)
{
    ESP_LOGI(TAG, "PCCOM ESP32-WROOM-32 scaffold ready");
    ESP_LOGI(TAG, "profile=%s idf=%s", PCCOM_PROFILE_NAME, esp_get_idf_version());

    while (1) {
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
