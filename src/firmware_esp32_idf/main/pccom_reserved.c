#include "pccom_reserved.h"

#include <stdio.h>
#include <string.h>

#include "esp_log.h"

static const char *TAG = "pccom-reserved";

static bool starts_with(const char *text, const char *prefix)
{
    return text != NULL && strncmp(text, prefix, strlen(prefix)) == 0;
}

bool pccom_is_reserved_namespace(const char *topic)
{
    return starts_with(topic, "commands/v1/") || starts_with(topic, "pccom/v1/");
}

void pccom_reserved_topics(const pccom_config_t *cfg, char *dim_topic,
                           size_t dim_size, char *result_topic, size_t result_size)
{
    if (cfg == NULL) {
        return;
    }
    if (dim_topic != NULL && dim_size > 0) {
        snprintf(dim_topic, dim_size, "commands/v1/%s/%s/%s/dim",
                 cfg->site_id, cfg->device_type, cfg->device_id);
    }
    if (result_topic != NULL && result_size > 0) {
        snprintf(result_topic, result_size, "commands/v1/%s/%s/%s/dim/result",
                 cfg->site_id, cfg->device_type, cfg->device_id);
    }
}

esp_err_t pccom_handle_reserved_command(const char *topic, const char *payload, size_t len)
{
    (void)payload;
    (void)len;
    ESP_LOGW(TAG, "namespace lệnh chỉ đặt chỗ ở S2, không xử lý: %s",
             topic != NULL ? topic : "(null)");
    return ESP_ERR_NOT_SUPPORTED;
}
