#ifndef PCCOM_PROVISION_H
#define PCCOM_PROVISION_H

#include "esp_err.h"
#include "pccom_config.h"

/* Chặn cho tới khi nhận được khung provisioning hợp lệ trên UART1.
 * Khung: PCCOM:<base64(TLV)>,<crc32hex>\n
 * TLV:   tag(1 byte) | length(2 byte, big endian) | value
 * CRC32 (IEEE, poly 0xEDB88320) tính trên bytes TLV đã decode.
 * UART1: RX=GPIO16, TX=GPIO17, 115200 8N1. */
esp_err_t pccom_provision_wait(pccom_config_t *out_cfg);

#endif /* PCCOM_PROVISION_H */
