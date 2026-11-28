#include "pccom_provision.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "driver/uart.h"
#include "esp_log.h"
#include "mbedtls/base64.h"

#include "pccom_config.h"
#include "pccom_nvs.h"

static const char *TAG = "pccom-provision";

#define PCCOM_UART UART_NUM_1
#define PCCOM_UART_RX_PIN 16
#define PCCOM_UART_TX_PIN 17
#define PCCOM_UART_BAUD 115200

#define PCCOM_FRAME_PREFIX "PCCOM:"
#define PCCOM_MAX_LINE (12288)
#define PCCOM_MAX_DECODED ((PCCOM_MAX_LINE * 3) / 4)

/* Tags TLV. Không đổi giá trị này khi đã phát hành tool provisioning.
 * tag 0 là version, bắt buộc đứng đầu khung để tool/host biết cách đóng gói. */
enum {
    TLV_VERSION = 0,
    TLV_SITE = 1,
    TLV_DEVICE_TYPE = 2,
    TLV_DEVICE_ID = 3,
    TLV_BROKER_HOST = 4,
    TLV_BROKER_PORT = 5,
    TLV_CA_PEM = 6,
    TLV_CLIENT_CERT = 7,
    TLV_CLIENT_KEY = 8,
    TLV_DEVICE_KEY = 9,   /* 32 byte, đã dẫn xuất trên host; KHÔNG phải master */
    TLV_WIFI_SSID = 10,
    TLV_WIFI_PASS = 11,
    TLV_CLIENT_ID = 12
};

static void send_reply(const char *text)
{
    uart_write_bytes(PCCOM_UART, text, strlen(text));
}

static uint32_t crc32_ieee(const uint8_t *data, size_t len)
{
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t i = 0; i < len; ++i) {
        crc ^= data[i];
        for (int bit = 0; bit < 8; ++bit) {
            uint32_t mask = (uint32_t)-(int32_t)(crc & 1u);
            crc = (crc >> 1) ^ (0xEDB88320u & mask);
        }
    }
    return ~crc;
}

static bool parse_crc_hex(const char *text, uint32_t *value)
{
    if (strlen(text) != 8) {
        return false;
    }
    uint32_t result = 0;
    for (int i = 0; i < 8; ++i) {
        char c = text[i];
        uint8_t nibble;
        if (c >= '0' && c <= '9') {
            nibble = (uint8_t)(c - '0');
        } else if (c >= 'a' && c <= 'f') {
            nibble = (uint8_t)(c - 'a' + 10);
        } else if (c >= 'A' && c <= 'F') {
            nibble = (uint8_t)(c - 'A' + 10);
        } else {
            return false;
        }
        result = (result << 4) | nibble;
    }
    *value = result;
    return true;
}

static bool valid_segment(const uint8_t *value, size_t len)
{
    if (len < 1 || len > 64) {
        return false;
    }
    for (size_t i = 0; i < len; ++i) {
        char c = (char)value[i];
        bool ok = (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
                  (c >= '0' && c <= '9') || c == '_' || c == '-';
        if (!ok) {
            return false;
        }
    }
    return true;
}

static bool copy_string(char *dst, size_t dst_size, const uint8_t *value, size_t len,
                        bool require_segment)
{
    if (len == 0 || len >= dst_size || value == NULL) {
        return false;
    }
    if (require_segment && !valid_segment(value, len)) {
        return false;
    }
    for (size_t i = 0; i < len; ++i) {
        if (value[i] == '\0') {
            return false;
        }
    }
    memcpy(dst, value, len);
    dst[len] = '\0';
    return true;
}

static bool copy_blob(uint8_t **dst, size_t *dst_len, const uint8_t *value, size_t len)
{
    if (len == 0 || *dst != NULL || value == NULL) {
        return false;
    }
    uint8_t *buf = malloc(len + 1);
    if (buf == NULL) {
        return false;
    }
    memcpy(buf, value, len);
    buf[len] = '\0';
    *dst = buf;
    *dst_len = len;
    return true;
}

static bool parse_tlv(const uint8_t *data, size_t len, pccom_config_t *cfg)
{
    size_t offset = 0;
    while (offset < len) {
        if (len - offset < 3) {
            return false;
        }
        uint8_t tag = data[offset++];
        size_t value_len = ((size_t)data[offset] << 8) | data[offset + 1];
        offset += 2;
        if (value_len > len - offset) {
            return false;
        }
        const uint8_t *value = data + offset;
        offset += value_len;

        /* TLV đầu tiên phải là version=1, length=1. Chặn khung cũ/không rõ
         * định dạng trước khi ghi bất cứ trường nào vào NVS. */
        if (offset == 3u + value_len) {
            if (tag != TLV_VERSION || value_len != 1 ||
                value[0] != PCCOM_PROVISION_VERSION) {
                ESP_LOGE(TAG, "khung provisioning sai version (cần tag=0 len=1 val=%u)",
                         (unsigned int)PCCOM_PROVISION_VERSION);
                return false;
            }
            continue;
        }

        bool ok = true;
        switch (tag) {
        case TLV_VERSION:
            ok = false; /* version chỉ được phép ở TLV đầu tiên */
            break;
        case TLV_SITE:
            ok = copy_string(cfg->site_id, sizeof(cfg->site_id), value, value_len, true);
            break;
        case TLV_DEVICE_TYPE:
            ok = copy_string(cfg->device_type, sizeof(cfg->device_type), value, value_len, true);
            break;
        case TLV_DEVICE_ID:
            ok = copy_string(cfg->device_id, sizeof(cfg->device_id), value, value_len, true);
            break;
        case TLV_CLIENT_ID:
            ok = copy_string(cfg->client_id, sizeof(cfg->client_id), value, value_len, true);
            break;
        case TLV_BROKER_HOST:
            ok = copy_string(cfg->broker_host, sizeof(cfg->broker_host), value, value_len, false);
            break;
        case TLV_BROKER_PORT:
            ok = value_len == 2;
            if (ok) {
                cfg->broker_port = (uint16_t)(((uint16_t)value[0] << 8) | value[1]);
            }
            break;
        case TLV_WIFI_SSID:
            ok = copy_string(cfg->wifi_ssid, sizeof(cfg->wifi_ssid), value, value_len, false);
            break;
        case TLV_WIFI_PASS:
            ok = copy_string(cfg->wifi_pass, sizeof(cfg->wifi_pass), value, value_len, false);
            break;
        case TLV_CA_PEM:
            ok = copy_blob((uint8_t **)&cfg->ca_pem, &cfg->ca_len, value, value_len);
            break;
        case TLV_CLIENT_CERT:
            ok = copy_blob((uint8_t **)&cfg->cert_pem, &cfg->cert_len, value, value_len);
            break;
        case TLV_CLIENT_KEY:
            ok = copy_blob((uint8_t **)&cfg->key_pem, &cfg->key_len, value, value_len);
            break;
        case TLV_DEVICE_KEY:
            /* Chấp nhận đúng 32 byte. Không log giá trị; key là dữ liệu nhạy cảm. */
            ok = value_len == sizeof(cfg->device_key);
            if (ok) {
                memcpy(cfg->device_key, value, value_len);
                cfg->has_device_key = true;
            }
            break;
        default:
            ESP_LOGW(TAG, "bỏ qua TLV tag=%u len=%u không xác định", (unsigned int)tag,
                 (unsigned int)value_len);
            break;
        }
        if (!ok) {
            ESP_LOGE(TAG, "TLV tag=%u len=%u không hợp lệ", (unsigned int)tag,
                 (unsigned int)value_len);
            return false;
        }
    }

    if (cfg->broker_port == 0) {
        return false;
    }
    return true;
}

esp_err_t pccom_provision_wait(pccom_config_t *out_cfg)
{
    if (out_cfg == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    uart_config_t uart_cfg = {
        .baud_rate = PCCOM_UART_BAUD,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    /* 8192 byterx buffer: đủ cho một dòng ~4KB (base64 PEM/chunk) không mất byte. */
    esp_err_t err = uart_driver_install(PCCOM_UART, 8192, 0, 0, NULL, 0);
    if (err != ESP_OK) {
        return err;
    }
    err = uart_param_config(PCCOM_UART, &uart_cfg);
    if (err == ESP_OK) {
        err = uart_set_pin(PCCOM_UART, PCCOM_UART_TX_PIN, PCCOM_UART_RX_PIN,
                           UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
    }
    if (err != ESP_OK) {
        uart_driver_delete(PCCOM_UART);
        return err;
    }

    char *line = malloc(PCCOM_MAX_LINE + 1);
    uint8_t *decoded = malloc(PCCOM_MAX_DECODED);
    if (line == NULL || decoded == NULL) {
        free(line);
        free(decoded);
        uart_driver_delete(PCCOM_UART);
        return ESP_ERR_NO_MEM;
    }

    ESP_LOGI(TAG, "chờ provisioning UART1 RX=GPIO%d TX=GPIO%d %d 8N1",
             PCCOM_UART_RX_PIN, PCCOM_UART_TX_PIN, PCCOM_UART_BAUD);
    send_reply("+READY\n");

    size_t line_len = 0;
    size_t assembled_len = 0;
    size_t assembled_chunks = 0;
    size_t expected_chunks = 0;
    int idle_ms = 0;
    for (;;) {
        uint8_t ch = 0;
        int read_len = uart_read_bytes(PCCOM_UART, &ch, 1,
                                       pdMS_TO_TICKS(PCCOM_POLL_TICK_MS));
        if (read_len <= 0) {
            idle_ms += PCCOM_POLL_TICK_MS;
            if (idle_ms >= PCCOM_PROVISION_IDLE_TIMEOUT_MS) {
                send_reply("-ERR TIMEOUT\n");
                ESP_LOGE(TAG, "provisioning timeout: không có dữ liệu trong %dms",
                         idle_ms);
                free(line);
                free(decoded);
                uart_driver_delete(PCCOM_UART);
                return ESP_ERR_TIMEOUT;
            }
            continue;
        }
        idle_ms = 0;
        if (ch == '\n') {
            while (line_len > 0 && (line[line_len - 1] == '\r' || line[line_len - 1] == ' ')) {
                line[--line_len] = '\0';
            }
            if (line_len == 0) {
                continue;
            }
            line[line_len] = '\0';

            esp_err_t result = ESP_FAIL;
            const char *reason = "BAD_FRAME";
            bool handled_chunk = false;
            bool chunked_line = false;

            const size_t prefix_len = strlen(PCCOM_FRAME_PREFIX);
            if (strncmp(line, PCCOM_FRAME_PREFIX, prefix_len) == 0) {
                char *body = line + prefix_len;

                /* Khung chunked: PCCOM:C<seq>/<total>:<b64>,<crc32 chunk> rồi
                 * PCCOM:S<crc32 tổng>. CRC từng chunk được kiểm chứng trước khi
                 * ghép; CRC tổng được kiểm chứng trước khi parse TLV/ghi NVS. */
                if (body[0] == 'C' || body[0] == 'S') {
                    chunked_line = true;
                    char *comma = strchr(body, ',');
                    if (comma != NULL) {
                        *comma = '\0';
                    }
                    if (body[0] == 'C') {
                        char *colon = strchr(body + 1, ':');
                        char *slash = colon != NULL ? strchr(body + 1, '/') : NULL;
                        uint32_t chunk_crc = 0;
                        if (colon == NULL || slash == NULL || comma == NULL ||
                            slash > colon) {
                            reason = "BAD_FRAME";
                        } else {
                            *colon = '\0';
                            *slash = '\0';
                            int seq = atoi(body + 1);
                            int total = atoi(slash + 1);
                            if (seq < 1 || total < 1 || seq > total ||
                                (expected_chunks != 0 && (size_t)total != expected_chunks) ||
                                (size_t)seq != assembled_chunks + 1) {
                                reason = "BAD_FRAME";
                            } else if (!parse_crc_hex(comma + 1, &chunk_crc)) {
                                reason = "BAD_FRAME";
                            } else {
                                size_t out_len = 0;
                                int b64_ret = mbedtls_base64_decode(
                                    decoded + assembled_len,
                                    PCCOM_MAX_DECODED - assembled_len, &out_len,
                                    (const unsigned char *)(colon + 1),
                                    strlen(colon + 1));
                                if (b64_ret != 0) {
                                    reason = "BAD_BASE64";
                                } else if (crc32_ieee(decoded + assembled_len,
                                                      out_len) != chunk_crc) {
                                    reason = "CRC_MISMATCH";
                                } else {
                                    assembled_len += out_len;
                                    assembled_chunks++;
                                    expected_chunks = (size_t)total;
                                    handled_chunk = true;
                                    result = ESP_OK;
                                }
                            }
                        }
                    } else if (comma == NULL) {
                        reason = "BAD_FRAME";
                    } else {
                        uint32_t total_crc = 0;
                        if (!parse_crc_hex(body + 1, &total_crc)) {
                            reason = "BAD_FRAME";
                        } else if (expected_chunks == 0 ||
                                   assembled_chunks != expected_chunks) {
                            reason = "BAD_FRAME";
                        } else if (crc32_ieee(decoded, assembled_len) != total_crc) {
                            reason = "CRC_MISMATCH_TOTAL";
                        } else {
                            pccom_config_t candidate;
                            memset(&candidate, 0, sizeof(candidate));
                            if (!parse_tlv(decoded, assembled_len, &candidate)) {
                                reason = "BAD_TLV";
                                pccom_config_free(&candidate);
                            } else if (!pccom_config_is_valid(&candidate)) {
                                reason = "MISSING_FIELD";
                                pccom_config_free(&candidate);
                            } else {
                                result = pccom_nvs_save(&candidate);
                                pccom_config_free(&candidate);
                                reason = "NVS_FAIL";
                            }
                        }
                    }
                    goto line_done;
                }

                char *comma = strchr(line + prefix_len, ',');
                if (comma != NULL) {
                    *comma = '\0';
                    const char *b64 = line + prefix_len;
                    const char *crc_text = comma + 1;
                    uint32_t expected_crc = 0;
                    size_t decoded_len = 0;

                    int b64_ret = mbedtls_base64_decode(decoded, PCCOM_MAX_DECODED,
                                                        &decoded_len,
                                                        (const unsigned char *)b64,
                                                        strlen(b64));
                    if (b64_ret != 0) {
                        reason = "BAD_BASE64";
                    } else if (!parse_crc_hex(crc_text, &expected_crc)) {
                        reason = "BAD_FRAME";
                    } else if (crc32_ieee(decoded, decoded_len) != expected_crc) {
                        reason = "CRC_MISMATCH";
                    } else {
                        pccom_config_t candidate;
                        memset(&candidate, 0, sizeof(candidate));
                        if (!parse_tlv(decoded, decoded_len, &candidate)) {
                            reason = "BAD_TLV";
                            pccom_config_free(&candidate);
                        } else if (!pccom_config_is_valid(&candidate)) {
                            reason = "MISSING_FIELD";
                            pccom_config_free(&candidate);
                        } else {
                            result = pccom_nvs_save(&candidate);
                            pccom_config_free(&candidate);
                            reason = "NVS_FAIL";
                        }
                    }
                }
            }

line_done:
            line_len = 0;
            if (handled_chunk && result == ESP_OK) {
                send_reply("+OK\n");
                continue;
            }
            if (result == ESP_OK) {
                send_reply("+ACK\n");
                ESP_LOGI(TAG, "provisioning thành công; đã lưu vào NVS");
                free(line);
                free(decoded);
                uart_driver_delete(PCCOM_UART);
                return ESP_OK;
            }
            if (chunked_line) {
                /* Một chunk/summary hỏng: bỏ toàn bộ khung, bắt đầu lại từ đầu. */
                assembled_len = 0;
                assembled_chunks = 0;
                expected_chunks = 0;
            }
            char reply[48];
            snprintf(reply, sizeof(reply), "-ERR %s\n", reason);
            send_reply(reply);
            ESP_LOGW(TAG, "provisioning bị từ chối: %s", reason);
            continue;
        }

        if (line_len >= PCCOM_MAX_LINE) {
            line_len = 0;
            send_reply("-ERR BAD_FRAME\n");
            ESP_LOGW(TAG, "khung provisioning quá dài, đã bỏ qua");
            continue;
        }
        line[line_len++] = (char)ch;
    }
}
