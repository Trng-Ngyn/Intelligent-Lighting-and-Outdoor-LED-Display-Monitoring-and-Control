#include "pccom_network.h"

#include <stdio.h>
#include <string.h>

#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_sntp.h"
#include "esp_task_wdt.h"
#include "esp_wifi.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "mqtt_client.h"

#if defined(CONFIG_MQTT_PROTOCOL_5)
#include "mqtt5_client.h"
#else
#error "S2 cần CONFIG_MQTT_PROTOCOL_5=y trong sdkconfig.defaults.common"
#endif

#include "pccom_reserved.h"
#include "pccom_security.h"

static const char *TAG = "pccom-network";

static SemaphoreHandle_t g_publish_mutex;
static esp_mqtt_client_handle_t g_client;
static const pccom_config_t *s_cfg;
static pccom_context_t *s_ctx;
static uint8_t s_device_key[32];
static pccom_publish_item_t s_will_item;

static void wifi_event_handler(void *arg, esp_event_base_t event_base,
                               int32_t event_id, void *event_data)
{
    (void)event_data;
    pccom_context_t *ctx = (pccom_context_t *)arg;
    if (ctx == NULL) {
        return;
    }
    if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ESP_LOGI(TAG, "WiFi STA đã có IP");
        xEventGroupSetBits(ctx->events, PCCOM_WIFI_CONNECTED_BIT);
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        ESP_LOGW(TAG, "WiFi STA mất kết nối; thử lại");
        xEventGroupClearBits(ctx->events, PCCOM_WIFI_CONNECTED_BIT);
        xEventGroupClearBits(ctx->events, PCCOM_MQTT_CONNECTED_BIT);
        esp_wifi_connect();
    }
}

static void sntp_sync_callback(struct timeval *tv)
{
    (void)tv;
    if (s_ctx != NULL) {
        ESP_LOGI(TAG, "đồng bộ thời gian SNTP thành công");
        xEventGroupSetBits(s_ctx->events, PCCOM_SNTP_SYNCED_BIT);
    }
}

static esp_err_t make_status_item(const char *state, pccom_publish_item_t *item)
{
    if (s_cfg == NULL || state == NULL || item == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    char topic[PCCOM_TOPIC_MAX];
    char correlation_id[37];
    char ts_ms[21];
    char signature[65];

    snprintf(topic, sizeof(topic), "status/v1/%s/%s/%s",
             s_cfg->site_id, s_cfg->device_type, s_cfg->device_id);
    pccom_new_uuid4(correlation_id);
    if (!pccom_epoch_ms(ts_ms)) {
        return ESP_FAIL;
    }
    esp_err_t err = pccom_sign_message(s_device_key, topic, correlation_id, ts_ms,
                                       state, signature);
    if (err != ESP_OK) {
        return err;
    }

    memset(item, 0, sizeof(*item));
    strncpy(item->topic, topic, sizeof(item->topic) - 1);
    strncpy(item->payload, state, sizeof(item->payload) - 1);
    strncpy(item->correlation_id, correlation_id, sizeof(item->correlation_id) - 1);
    strncpy(item->ts_ms, ts_ms, sizeof(item->ts_ms) - 1);
    strncpy(item->signature, signature, sizeof(item->signature) - 1);
    item->qos = PCCOM_MQTT_QOS;
    item->retain = 1;
    return ESP_OK;
}

static esp_err_t publish_item(const pccom_publish_item_t *item)
{
    if (g_client == NULL || g_publish_mutex == NULL || item == NULL) {
        return ESP_ERR_INVALID_STATE;
    }

    xSemaphoreTake(g_publish_mutex, portMAX_DELAY);

    esp_mqtt5_user_property_item_t props[3] = {
        { .key = "correlation_id", .value = item->correlation_id },
        { .key = "ts_ms", .value = item->ts_ms },
        { .key = "signature", .value = item->signature },
    };
    esp_mqtt5_publish_property_config_t publish_prop = {
        .payload_format_indicator = true,
        .content_type = item->retain ? "text/plain; charset=utf-8" : "application/json",
        .correlation_data = item->correlation_id,
        .correlation_data_len = (uint16_t)strlen(item->correlation_id),
        .user_property = NULL,
    };

    esp_err_t err = esp_mqtt5_client_set_user_property(&publish_prop.user_property,
                                                       props, 3);
    int msg_id = -1;
    if (err == ESP_OK) {
        err = esp_mqtt5_client_set_publish_property(g_client, &publish_prop);
    }
    if (err == ESP_OK) {
        msg_id = esp_mqtt_client_publish(g_client, item->topic, item->payload, 0,
                                         item->qos, item->retain);
    }
    if (publish_prop.user_property != NULL) {
        esp_mqtt5_client_delete_user_property(publish_prop.user_property);
    }
    xSemaphoreGive(g_publish_mutex);

    if (err != ESP_OK) {
        if (s_ctx != NULL) {
            s_ctx->publish_failures++;
        }
        ESP_LOGE(TAG, "đặt publish property failed: %s", esp_err_to_name(err));
        return err;
    }
    if (msg_id < 0) {
        if (s_ctx != NULL) {
            s_ctx->publish_failures++;
        }
        ESP_LOGE(TAG, "publish failed topic=%s", item->topic);
        return ESP_FAIL;
    }
    if (s_ctx != NULL) {
        s_ctx->published++;
    }
    ESP_LOGI(TAG, "publish topic=%s qos=%d retain=%d msg_id=%d",
             item->topic, item->qos, item->retain, msg_id);
    return ESP_OK;
}

static void mqtt_event_handler(void *handler_args, esp_event_base_t base,
                               int32_t event_id, void *event_data)
{
    (void)base;
    esp_mqtt_event_handle_t event = (esp_mqtt_event_handle_t)event_data;
    pccom_context_t *ctx = (pccom_context_t *)handler_args;

    switch (event_id) {
    case MQTT_EVENT_CONNECTED: {
        if (ctx != NULL) {
            xEventGroupSetBits(ctx->events, PCCOM_MQTT_CONNECTED_BIT);
        }
        ESP_LOGI(TAG, "MQTT 5 đã kết nối; keepalive=%ds", PCCOM_MQTT_KEEPALIVE_SEC);

        pccom_publish_item_t online;
        if (make_status_item("online", &online) == ESP_OK) {
            esp_err_t err = publish_item(&online);
            if (err != ESP_OK) {
                ESP_LOGE(TAG, "publish status online failed: %s", esp_err_to_name(err));
            }
        }
        break;
    }
    case MQTT_EVENT_DISCONNECTED:
        if (ctx != NULL) {
            xEventGroupClearBits(ctx->events, PCCOM_MQTT_CONNECTED_BIT);
        }
        ESP_LOGW(TAG, "MQTT mất kết nối; esp-mqtt sẽ tự reconnect");
        break;
    case MQTT_EVENT_DATA: {
        /* S2 không subscribe; nhánh này chỉ để handler lệnh đặt chỗ không bị
         * kích hoạt ngoài ý định nếu W5 bật subscribe mà quên cập nhật. */
        char topic[PCCOM_TOPIC_MAX];
        size_t topic_len = (size_t)event->topic_len;
        if (topic_len >= sizeof(topic)) {
            topic_len = sizeof(topic) - 1;
        }
        if (topic_len > 0 && event->topic != NULL) {
            memcpy(topic, event->topic, topic_len);
        }
        topic[topic_len] = '\0';
        if (pccom_is_reserved_namespace(topic)) {
            pccom_handle_reserved_command(topic, event->data, (size_t)event->data_len);
        }
#if defined(CONFIG_MQTT_PROTOCOL_5)
        if (event->property != NULL && event->property->user_property != NULL) {
            esp_mqtt5_client_delete_user_property(event->property->user_property);
            event->property->user_property = NULL;
        }
#endif
        break;
    }
    case MQTT_EVENT_ERROR:
        ESP_LOGE(TAG, "MQTT_EVENT_ERROR error_type=%d",
                 event->error_handle != NULL ? event->error_handle->error_type : -1);
        break;
    default:
        break;
    }
}

static void log_runtime_counters(void)
{
    if (s_ctx == NULL) {
        return;
    }
    ESP_LOGI(TAG, "stats: published=%lu fail=%lu drop_pub=%lu drop_sample=%lu net_retry=%lu",
             (unsigned long)s_ctx->published,
             (unsigned long)s_ctx->publish_failures,
             (unsigned long)s_ctx->dropped_publishes,
             (unsigned long)s_ctx->dropped_samples,
             (unsigned long)s_ctx->net_retries);
}

static esp_err_t start_wifi_and_time(pccom_context_t *ctx)
{
    const pccom_config_t *cfg = ctx->cfg;

    esp_err_t err = esp_netif_init();
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) {
        return err;
    }
    err = esp_event_loop_create_default();
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) {
        return err;
    }
    if (esp_netif_create_default_wifi_sta() == NULL) {
        return ESP_ERR_NO_MEM;
    }

    wifi_init_config_t wifi_cfg = WIFI_INIT_CONFIG_DEFAULT();
    err = esp_wifi_init(&wifi_cfg);
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) {
        return err;
    }
    err = esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID,
                                              &wifi_event_handler, ctx, NULL);
    if (err != ESP_OK) {
        return err;
    }
    err = esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP,
                                              &wifi_event_handler, ctx, NULL);
    if (err != ESP_OK) {
        return err;
    }
    err = esp_wifi_set_mode(WIFI_MODE_STA);
    if (err != ESP_OK) {
        return err;
    }

    wifi_config_t sta_cfg;
    memset(&sta_cfg, 0, sizeof(sta_cfg));
    strncpy((char *)sta_cfg.sta.ssid, cfg->wifi_ssid, sizeof(sta_cfg.sta.ssid) - 1);
    strncpy((char *)sta_cfg.sta.password, cfg->wifi_pass, sizeof(sta_cfg.sta.password) - 1);
    err = esp_wifi_set_config(WIFI_IF_STA, &sta_cfg);
    if (err != ESP_OK) {
        return err;
    }
    err = esp_wifi_start();
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) {
        return err;
    }
    err = esp_wifi_connect();
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) {
        return err;
    }

    esp_sntp_set_sync_mode(SNTP_SYNC_MODE_IMMED);
    esp_sntp_setservername(0, "pool.ntp.org");
    esp_sntp_setservername(1, "time.google.com");
    esp_sntp_set_time_sync_notification_cb(&sntp_sync_callback);
    esp_sntp_init();

    ESP_LOGI(TAG, "đợi WiFi + SNTP tối đa %dms trước khi mở MQTT "
             "(ts_ms phải là epoch thật)", PCCOM_NET_WAIT_TIMEOUT_MS);
    const EventBits_t ready_bits =
        PCCOM_WIFI_CONNECTED_BIT | PCCOM_SNTP_SYNCED_BIT;
    int waited_ms = 0;
    int wifi_retry_at = PCCOM_WIFI_RETRY_MS;
    int sntp_retry_at = PCCOM_SNTP_RETRY_MS;
    int log_at = PCCOM_STATS_LOG_MS;
    for (;;) {
        (void)esp_task_wdt_reset();
        EventBits_t bits = xEventGroupWaitBits(
            ctx->events, ready_bits, pdFALSE, pdTRUE,
            pdMS_TO_TICKS(PCCOM_POLL_TICK_MS));
        if ((bits & ready_bits) == ready_bits) {
            ESP_LOGI(TAG, "WiFi + SNTP sẵn sàng sau %dms", waited_ms);
            return ESP_OK;
        }
        waited_ms += PCCOM_POLL_TICK_MS;

        if ((bits & PCCOM_WIFI_CONNECTED_BIT) == 0 &&
            waited_ms >= wifi_retry_at) {
            wifi_retry_at += PCCOM_WIFI_RETRY_MS;
            ctx->net_retries++;
            (void)esp_wifi_connect();
        }
        if ((bits & PCCOM_SNTP_SYNCED_BIT) == 0 &&
            waited_ms >= sntp_retry_at) {
            sntp_retry_at += PCCOM_SNTP_RETRY_MS;
            ctx->net_retries++;
            esp_sntp_stop();
            esp_sntp_set_time_sync_notification_cb(&sntp_sync_callback);
            esp_sntp_init();
            ESP_LOGW(TAG, "đổi lại SNTP sau %dms (retry=%lu)", waited_ms,
                     (unsigned long)ctx->net_retries);
        }
        if (waited_ms >= log_at) {
            log_at += PCCOM_STATS_LOG_MS;
            log_runtime_counters();
        }
        if (waited_ms >= PCCOM_NET_WAIT_TIMEOUT_MS) {
            ESP_LOGE(TAG, "timeout chờ WiFi+SNTP sau %dms; dừng Network Manager",
                     waited_ms);
            return ESP_ERR_TIMEOUT;
        }
    }
}

void pccom_network_task(void *arg)
{
    pccom_context_t *ctx = (pccom_context_t *)arg;
    if (ctx == NULL || !pccom_config_is_valid(ctx->cfg)) {
        (void)esp_task_wdt_delete(NULL); /* tránh entry TWDT của task đã chết */
        vTaskDelete(NULL);
        return;
    }

    s_ctx = ctx;
    s_cfg = ctx->cfg;
    g_publish_mutex = xSemaphoreCreateMutex();
    if (g_publish_mutex == NULL) {
        ESP_LOGE(TAG, "không tạo được publish mutex");
        (void)esp_task_wdt_delete(NULL); /* tránh entry TWDT của task đã chết */
        vTaskDelete(NULL);
        return;
    }

    esp_err_t err = pccom_derive_device_key(s_cfg, s_device_key);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "không dẫn xuất được device key: %s", esp_err_to_name(err));
        (void)esp_task_wdt_delete(NULL); /* tránh entry TWDT của task đã chết */
        vTaskDelete(NULL);
        return;
    }

    err = start_wifi_and_time(ctx);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "WiFi/SNTP khởi động failed: %s", esp_err_to_name(err));
        (void)esp_task_wdt_delete(NULL); /* tránh entry TWDT của task đã chết */
        vTaskDelete(NULL);
        return;
    }

    err = make_status_item("offline", &s_will_item);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "không ký được LWT: %s", esp_err_to_name(err));
        (void)esp_task_wdt_delete(NULL); /* tránh entry TWDT của task đã chết */
        vTaskDelete(NULL);
        return;
    }

    char broker_uri[PCCOM_HOST_MAX + 32];
    snprintf(broker_uri, sizeof(broker_uri), "mqtts://%s:%u",
             s_cfg->broker_host, (unsigned int)s_cfg->broker_port);

    esp_mqtt_client_config_t mqtt_cfg = {
        .broker.address.uri = broker_uri,
        .broker.verification.certificate = s_cfg->ca_pem,
        .broker.verification.certificate_len = s_cfg->ca_len,
        .credentials.username = s_cfg->client_id,
        .credentials.client_id = s_cfg->client_id,
        .credentials.authentication.certificate = s_cfg->cert_pem,
        .credentials.authentication.certificate_len = s_cfg->cert_len,
        .credentials.authentication.key = s_cfg->key_pem,
        .credentials.authentication.key_len = s_cfg->key_len,
        .session.last_will.topic = s_will_item.topic,
        .session.last_will.msg = s_will_item.payload,
        .session.last_will.msg_len = (int)strlen(s_will_item.payload),
        .session.last_will.qos = PCCOM_MQTT_QOS,
        .session.last_will.retain = 1,
        .session.keepalive = PCCOM_MQTT_KEEPALIVE_SEC,
        .session.protocol_ver = MQTT_PROTOCOL_V_5,
        .network.reconnect_timeout_ms = 5000,
        .task.stack_size = 8192,
        .buffer.size = 2048,
        .buffer.out_size = 2048,
    };

    g_client = esp_mqtt_client_init(&mqtt_cfg);
    if (g_client == NULL) {
        ESP_LOGE(TAG, "esp_mqtt_client_init failed");
        (void)esp_task_wdt_delete(NULL); /* tránh entry TWDT của task đã chết */
        vTaskDelete(NULL);
        return;
    }

    /* Will Delay Interval = 0, Session Expiry = 0; User Properties của Will
     * gồm đủ correlation_id/ts_ms/signature như mọi bản tin khác. */
    esp_mqtt5_connection_property_config_t connect_prop = {
        .session_expiry_interval = 0,
        .will_delay_interval = PCCOM_WILL_DELAY_SEC,
        .payload_format_indicator = true,
        .content_type = "text/plain; charset=utf-8",
        .request_problem_info = true,
        .user_property = NULL,
        .will_user_property = NULL,
    };
    esp_mqtt5_user_property_item_t will_props[3] = {
        { .key = "correlation_id", .value = s_will_item.correlation_id },
        { .key = "ts_ms", .value = s_will_item.ts_ms },
        { .key = "signature", .value = s_will_item.signature },
    };
    err = esp_mqtt5_client_set_user_property(&connect_prop.will_user_property,
                                             will_props, 3);
    if (err == ESP_OK) {
        err = esp_mqtt5_client_set_connect_property(g_client, &connect_prop);
    }
    if (connect_prop.will_user_property != NULL) {
        esp_mqtt5_client_delete_user_property(connect_prop.will_user_property);
        connect_prop.will_user_property = NULL;
    }
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "đặt MQTT 5 connect property failed: %s", esp_err_to_name(err));
        esp_mqtt_client_destroy(g_client);
        g_client = NULL;
        (void)esp_task_wdt_delete(NULL); /* tránh entry TWDT của task đã chết */
        vTaskDelete(NULL);
        return;
    }

    err = esp_mqtt_client_register_event(g_client, ESP_EVENT_ANY_ID,
                                         &mqtt_event_handler, ctx);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "register MQTT event failed: %s", esp_err_to_name(err));
        esp_mqtt_client_destroy(g_client);
        g_client = NULL;
        (void)esp_task_wdt_delete(NULL); /* tránh entry TWDT của task đã chết */
        vTaskDelete(NULL);
        return;
    }
    err = esp_mqtt_client_start(g_client);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "start MQTT failed: %s", esp_err_to_name(err));
        esp_mqtt_client_destroy(g_client);
        g_client = NULL;
        (void)esp_task_wdt_delete(NULL); /* tránh entry TWDT của task đã chết */
        vTaskDelete(NULL);
        return;
    }

    ESP_LOGI(TAG, "Network Manager sẵn sàng; broker=%s port=%u",
             s_cfg->broker_host, (unsigned int)s_cfg->broker_port);

    pccom_publish_item_t item;
    TickType_t next_stats = xTaskGetTickCount() + pdMS_TO_TICKS(PCCOM_STATS_LOG_MS);
    for (;;) {
        (void)esp_task_wdt_reset();
        if (xTaskGetTickCount() >= next_stats) {
            next_stats += pdMS_TO_TICKS(PCCOM_STATS_LOG_MS);
            log_runtime_counters();
        }
        if (xQueueReceive(ctx->publish_queue, &item,
                          pdMS_TO_TICKS(PCCOM_POLL_TICK_MS)) != pdTRUE) {
            continue;
        }
        EventBits_t bits = xEventGroupGetBits(ctx->events);
        if ((bits & PCCOM_MQTT_CONNECTED_BIT) == 0) {
            ctx->dropped_publishes++;
            ESP_LOGW(TAG, "bỏ bản tin %s: MQTT chưa kết nối (không đệm offline)",
                     item.topic);
            continue;
        }
        (void)publish_item(&item);
    }
}
