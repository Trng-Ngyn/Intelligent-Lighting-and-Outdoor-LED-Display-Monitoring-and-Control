#ifndef PCCOM_TELEMETRY_H
#define PCCOM_TELEMETRY_H

#include "pccom_config.h"

/* Telemetry task: nhịp 10s, chỉ gửi yêu cầu lấy mẫu vào q_sample_req. */
void pccom_telemetry_task(void *arg);

/* Ingestion task: nhận q_sample_req, dựng payload Annex C, ký HMAC và
 * đẩy bản tin đã ký vào q_publish. Không trực tiếp gọi MQTT. */
void pccom_ingestion_task(void *arg);

#endif /* PCCOM_TELEMETRY_H */
