#ifndef PCCOM_SECURITY_H
#define PCCOM_SECURITY_H

#include <stdbool.h>
#include <stdint.h>

#include "esp_err.h"
#include "pccom_config.h"

/* device_key = HMAC-SHA256(master_secret, "{site}/{device_type}/{device_id}") */
esp_err_t pccom_derive_device_key(const pccom_config_t *cfg, uint8_t key[32]);

/* canonical = "v1\n{topic}\n{correlation_id}\n{ts_ms}\n{payload}" */
esp_err_t pccom_sign_message(const uint8_t key[32], const char *topic,
                             const char *correlation_id, const char *ts_ms,
                             const char *payload, char signature_hex[65]);

void pccom_new_uuid4(char out[37]);
bool pccom_epoch_ms(char out[21]);

/* Vector công khai do src/iot_protocol/signing.py sinh ra; dùng để đối chiếu
 * HMAC C với Python ngay khi boot. Không phải secret field. */
bool pccom_security_selftest(void);

#endif /* PCCOM_SECURITY_H */
