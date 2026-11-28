#ifndef PCCOM_RESERVED_H
#define PCCOM_RESERVED_H

#include <stdbool.h>
#include <stddef.h>

#include "esp_err.h"
#include "pccom_config.h"

/* S2 chỉ publish telemetry/status. Các namespace lệnh được đặt chỗ để W5 bật
 * sau mà không phải đổi topic/ACL; firmware hiện tại KHÔNG subscribe chúng. */
bool pccom_is_reserved_namespace(const char *topic);
void pccom_reserved_topics(const pccom_config_t *cfg, char *dim_topic,
                           size_t dim_size, char *result_topic, size_t result_size);

/* Handler đặt chỗ: luôn từ chối ở S2. Không sinh ra bản tin result. */
esp_err_t pccom_handle_reserved_command(const char *topic, const char *payload, size_t len);

#endif /* PCCOM_RESERVED_H */
