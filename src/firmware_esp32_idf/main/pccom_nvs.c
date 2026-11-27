#include "pccom_nvs.h"

#include <stdlib.h>
#include <string.h>

#include "esp_log.h"
#include "nvs.h"
#include "nvs_flash.h"

static const char *TAG = "pccom-nvs";

/* Các key trong namespace pccom_cfg. Chỉ là tên khóa, không phải secret. */
static const char *KEY_SITE = "site";
static const char *KEY_TYPE = "dtype";
static const char *KEY_DEVICE = "device";
static const char *KEY_CLIENT = "client";
static const char *KEY_HOST = "host";
static const char *KEY_PORT = "port";
static const char *KEY_SSID = "ssid";
static const char *KEY_PASS = "pass";
static const char *KEY_CA = "ca_pem";
static const char *KEY_CERT = "cert_pem";
static const char *KEY_KEY = "key_pem";
static const char *KEY_SECRET = "sign_secret";

static esp_err_t open_namespace(nvs_open_mode_t mode, nvs_handle_t *handle)
{
    esp_err_t err = nvs_open_from_partition(PCCOM_NVS_PARTITION, PCCOM_NVS_NAMESPACE, mode, handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "nvs_open failed: %s", esp_err_to_name(err));
    }
    return err;
}

static esp_err_t read_str(nvs_handle_t h, const char *key, char *dst, size_t dst_size)
{
    size_t len = dst_size;
    esp_err_t err = nvs_get_str(h, key, dst, &len);
    if (err != ESP_OK || len == 0 || len > dst_size) {
        return err == ESP_OK ? ESP_ERR_INVALID_SIZE : err;
    }
    dst[len - 1] = '\0';
    return ESP_OK;
}

static esp_err_t read_blob(nvs_handle_t h, const char *key, uint8_t **out, size_t *out_len)
{
    size_t len = 0;
    esp_err_t err = nvs_get_blob(h, key, NULL, &len);
    if (err != ESP_OK || len == 0) {
        return err == ESP_OK ? ESP_ERR_NOT_FOUND : err;
    }

    uint8_t *buf = malloc(len + 1);
    if (buf == NULL) {
        return ESP_ERR_NO_MEM;
    }
    err = nvs_get_blob(h, key, buf, &len);
    if (err != ESP_OK) {
        free(buf);
        return err;
    }
    buf[len] = '\0';
    *out = buf;
    *out_len = len;
    return ESP_OK;
}

void pccom_config_free(pccom_config_t *cfg)
{
    if (cfg == NULL) {
        return;
    }
    if (cfg->ca_pem != NULL) {
        free(cfg->ca_pem);
        cfg->ca_pem = NULL;
    }
    if (cfg->cert_pem != NULL) {
        free(cfg->cert_pem);
        cfg->cert_pem = NULL;
    }
    if (cfg->key_pem != NULL) {
        free(cfg->key_pem);
        cfg->key_pem = NULL;
    }
    if (cfg->signing_secret != NULL) {
        /* Xóa byte secret khỏi heap trước khi trả lại allocator. */
        memset(cfg->signing_secret, 0, cfg->signing_secret_len);
        free(cfg->signing_secret);
        cfg->signing_secret = NULL;
    }
    cfg->ca_len = 0;
    cfg->cert_len = 0;
    cfg->key_len = 0;
    cfg->signing_secret_len = 0;
}

bool pccom_config_is_valid(const pccom_config_t *cfg)
{
    return cfg != NULL && cfg->site_id[0] != '\0' && cfg->device_type[0] != '\0' &&
           cfg->device_id[0] != '\0' && cfg->client_id[0] != '\0' &&
           cfg->broker_host[0] != '\0' && cfg->broker_port != 0 &&
           cfg->wifi_ssid[0] != '\0' && cfg->ca_pem != NULL && cfg->ca_len > 0 &&
           cfg->cert_pem != NULL && cfg->cert_len > 0 && cfg->key_pem != NULL &&
           cfg->key_len > 0 && cfg->signing_secret != NULL &&
           cfg->signing_secret_len > 0;
}

esp_err_t pccom_nvs_init(void)
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_LOGW(TAG, "NVS cần khởi tạo lại: %s", esp_err_to_name(err));
        err = nvs_flash_erase();
        if (err == ESP_OK) {
            err = nvs_flash_init();
        }
    }
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "nvs_flash_init failed: %s", esp_err_to_name(err));
    }
    return err;
}

bool pccom_nvs_has_config(void)
{
    nvs_handle_t h;
    if (open_namespace(NVS_READONLY, &h) != ESP_OK) {
        return false;
    }
    size_t len = 0;
    esp_err_t err = nvs_get_str(h, KEY_SITE, NULL, &len);
    if (err == ESP_OK) {
        err = nvs_get_blob(h, KEY_SECRET, NULL, &len);
    }
    nvs_close(h);
    return err == ESP_OK;
}

esp_err_t pccom_nvs_load(pccom_config_t *cfg)
{
    if (cfg == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    memset(cfg, 0, sizeof(*cfg));

    nvs_handle_t h;
    esp_err_t err = open_namespace(NVS_READONLY, &h);
    if (err != ESP_OK) {
        return err;
    }

    err = read_str(h, KEY_SITE, cfg->site_id, sizeof(cfg->site_id));
    if (err == ESP_OK) err = read_str(h, KEY_TYPE, cfg->device_type, sizeof(cfg->device_type));
    if (err == ESP_OK) err = read_str(h, KEY_DEVICE, cfg->device_id, sizeof(cfg->device_id));
    if (err == ESP_OK) err = read_str(h, KEY_CLIENT, cfg->client_id, sizeof(cfg->client_id));
    if (err == ESP_OK) err = read_str(h, KEY_HOST, cfg->broker_host, sizeof(cfg->broker_host));
    if (err == ESP_OK) err = nvs_get_u16(h, KEY_PORT, &cfg->broker_port);
    if (err == ESP_OK) err = read_str(h, KEY_SSID, cfg->wifi_ssid, sizeof(cfg->wifi_ssid));
    if (err == ESP_OK) err = read_str(h, KEY_PASS, cfg->wifi_pass, sizeof(cfg->wifi_pass));

    if (err == ESP_OK) {
        err = read_blob(h, KEY_CA, (uint8_t **)&cfg->ca_pem, &cfg->ca_len);
    }
    if (err == ESP_OK) {
        err = read_blob(h, KEY_CERT, (uint8_t **)&cfg->cert_pem, &cfg->cert_len);
    }
    if (err == ESP_OK) {
        err = read_blob(h, KEY_KEY, (uint8_t **)&cfg->key_pem, &cfg->key_len);
    }
    if (err == ESP_OK) {
        err = read_blob(h, KEY_SECRET, &cfg->signing_secret, &cfg->signing_secret_len);
    }
    nvs_close(h);

    if (err != ESP_OK) {
        pccom_config_free(cfg);
        ESP_LOGE(TAG, "đọc cấu hình failed: %s", esp_err_to_name(err));
        return err;
    }
    if (!pccom_config_is_valid(cfg)) {
        pccom_config_free(cfg);
        return ESP_ERR_INVALID_STATE;
    }

    ESP_LOGI(TAG, "cấu hình đã nạp: site=%s type=%s device=%s client=%s",
             cfg->site_id, cfg->device_type, cfg->device_id, cfg->client_id);
    return ESP_OK;
}

esp_err_t pccom_nvs_save(const pccom_config_t *cfg)
{
    if (!pccom_config_is_valid(cfg)) {
        return ESP_ERR_INVALID_ARG;
    }

    nvs_handle_t h;
    esp_err_t err = open_namespace(NVS_READWRITE, &h);
    if (err != ESP_OK) {
        return err;
    }

    err = nvs_set_str(h, KEY_SITE, cfg->site_id);
    if (err == ESP_OK) err = nvs_set_str(h, KEY_TYPE, cfg->device_type);
    if (err == ESP_OK) err = nvs_set_str(h, KEY_DEVICE, cfg->device_id);
    if (err == ESP_OK) err = nvs_set_str(h, KEY_CLIENT, cfg->client_id);
    if (err == ESP_OK) err = nvs_set_str(h, KEY_HOST, cfg->broker_host);
    if (err == ESP_OK) err = nvs_set_u16(h, KEY_PORT, cfg->broker_port);
    if (err == ESP_OK) err = nvs_set_str(h, KEY_SSID, cfg->wifi_ssid);
    if (err == ESP_OK) err = nvs_set_str(h, KEY_PASS, cfg->wifi_pass);
    if (err == ESP_OK) err = nvs_set_blob(h, KEY_CA, cfg->ca_pem, cfg->ca_len);
    if (err == ESP_OK) err = nvs_set_blob(h, KEY_CERT, cfg->cert_pem, cfg->cert_len);
    if (err == ESP_OK) err = nvs_set_blob(h, KEY_KEY, cfg->key_pem, cfg->key_len);
    if (err == ESP_OK) {
        err = nvs_set_blob(h, KEY_SECRET, cfg->signing_secret, cfg->signing_secret_len);
    }
    if (err == ESP_OK) {
        err = nvs_commit(h);
    }
    nvs_close(h);

    if (err != ESP_OK) {
        ESP_LOGE(TAG, "lưu cấu hình failed: %s", esp_err_to_name(err));
        return err;
    }
    ESP_LOGI(TAG, "đã lưu cấu hình vào NVS (secret/PEM không được log)");
    return ESP_OK;
}

esp_err_t pccom_nvs_next_sequence(uint32_t *sequence)
{
    if (sequence == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    nvs_handle_t h;
    esp_err_t err = nvs_open_from_partition(PCCOM_NVS_PARTITION, PCCOM_RUNTIME_NAMESPACE,
                                            NVS_READWRITE, &h);
    if (err != ESP_OK) {
        return err;
    }

    uint32_t seq = 0;
    err = nvs_get_u32(h, "seq", &seq);
    if (err == ESP_ERR_NVS_NOT_FOUND) {
        err = ESP_OK;
    }
    if (err == ESP_OK) {
        seq += 1;
        err = nvs_set_u32(h, "seq", seq);
    }
    if (err == ESP_OK) {
        err = nvs_commit(h);
    }
    nvs_close(h);

    if (err != ESP_OK) {
        return err;
    }
    *sequence = seq;
    return ESP_OK;
}
