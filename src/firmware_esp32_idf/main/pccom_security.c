#include "pccom_security.h"

#include <stdio.h>
#include <string.h>
#include <sys/time.h>
#include <time.h>

#include "esp_log.h"
#include "esp_random.h"
#include "mbedtls/md.h"

static const char *TAG = "pccom-security";

esp_err_t pccom_copy_device_key(const pccom_config_t *cfg, uint8_t key[32])
{
    if (cfg == NULL || !cfg->has_device_key || key == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    memcpy(key, cfg->device_key, sizeof(cfg->device_key));
    return ESP_OK;
}

esp_err_t pccom_sign_message(const uint8_t key[32], const char *topic,
                             const char *correlation_id, const char *ts_ms,
                             const char *payload, char signature_hex[65])
{
    if (key == NULL || topic == NULL || correlation_id == NULL || ts_ms == NULL ||
        payload == NULL || signature_hex == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    const mbedtls_md_info_t *info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
    if (info == NULL) {
        return ESP_ERR_NOT_SUPPORTED;
    }

    mbedtls_md_context_t ctx;
    uint8_t digest[32];
    mbedtls_md_init(&ctx);
    int ret = mbedtls_md_setup(&ctx, info, 1);
    if (ret == 0) {
        ret = mbedtls_md_hmac_starts(&ctx, key, 32);
    }
    if (ret == 0) {
        ret = mbedtls_md_hmac_update(&ctx, (const unsigned char *)"v1\n", 3);
    }
    if (ret == 0) {
        ret = mbedtls_md_hmac_update(&ctx, (const unsigned char *)topic, strlen(topic));
    }
    if (ret == 0) {
        ret = mbedtls_md_hmac_update(&ctx, (const unsigned char *)"\n", 1);
    }
    if (ret == 0) {
        ret = mbedtls_md_hmac_update(&ctx, (const unsigned char *)correlation_id,
                                     strlen(correlation_id));
    }
    if (ret == 0) {
        ret = mbedtls_md_hmac_update(&ctx, (const unsigned char *)"\n", 1);
    }
    if (ret == 0) {
        ret = mbedtls_md_hmac_update(&ctx, (const unsigned char *)ts_ms, strlen(ts_ms));
    }
    if (ret == 0) {
        ret = mbedtls_md_hmac_update(&ctx, (const unsigned char *)"\n", 1);
    }
    if (ret == 0) {
        ret = mbedtls_md_hmac_update(&ctx, (const unsigned char *)payload, strlen(payload));
    }
    if (ret == 0) {
        ret = mbedtls_md_hmac_finish(&ctx, digest);
    }
    mbedtls_md_free(&ctx);

    if (ret != 0) {
        ESP_LOGE(TAG, "HMAC sign failed: -0x%04x", (unsigned int)-ret);
        return ESP_FAIL;
    }

    static const char hex[] = "0123456789abcdef";
    for (size_t i = 0; i < sizeof(digest); ++i) {
        signature_hex[i * 2] = hex[digest[i] >> 4];
        signature_hex[i * 2 + 1] = hex[digest[i] & 0x0fu];
    }
    signature_hex[64] = '\0';
    return ESP_OK;
}

void pccom_new_uuid4(char out[37])
{
    uint32_t words[4] = {
        esp_random(), esp_random(), esp_random(), esp_random()
    };
    uint8_t bytes[16];
    for (size_t i = 0; i < sizeof(bytes); ++i) {
        bytes[i] = (uint8_t)(words[i / 4] >> (8 * (i % 4)));
    }
    bytes[6] = (uint8_t)((bytes[6] & 0x0fu) | 0x40u);
    bytes[8] = (uint8_t)((bytes[8] & 0x3fu) | 0x80u);

    snprintf(out, 37,
             "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
             bytes[0], bytes[1], bytes[2], bytes[3], bytes[4], bytes[5], bytes[6],
             bytes[7], bytes[8], bytes[9], bytes[10], bytes[11], bytes[12], bytes[13],
             bytes[14], bytes[15]);
}

bool pccom_security_selftest(void)
{
    /* Public test vector: key là device key đã dẫn xuất (không phải master
     * secret; giá trị 0x00..0x1f chỉ là vector công khai để đối chiếu HMAC C
     * với Python). canonical = v1\n...\npccom-selftest-payload. */
    static const uint8_t key[32] = {
        0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
        0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f,
        0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17,
        0x18, 0x19, 0x1a, 0x1b, 0x1c, 0x1d, 0x1e, 0x1f,
    };
    const char *expected =
        "2b9f9552cb542dc3ca087f83e542826f8a88511e2fa2a63d1352472ac3a86836";
    char actual[65];

    esp_err_t err = pccom_sign_message(
        key,
        "telemetry/v1/SITE_01/light/LGT_NODE_001",
        "00000000-0000-4000-8000-000000000001",
        "1794660440618",
        "pccom-selftest-payload",
        actual);
    return err == ESP_OK && strcmp(actual, expected) == 0;
}

bool pccom_epoch_ms(char out[21])
{
    struct timeval tv;
    if (gettimeofday(&tv, NULL) != 0) {
        return false;
    }
    int64_t ms = (int64_t)tv.tv_sec * 1000 + tv.tv_usec / 1000;
    snprintf(out, 21, "%lld", (long long)ms);
    return true;
}
