#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

// ==========================================
// 1. DEVICE IDENTIFICATION (RFP LGT 01)
// ==========================================
#define TENANT_ID          "PCCOM_CORP"
#define SITE_ID            "SITE_01"
#define ASSET_ID           "LGT_NODE_001"
#define FIRMWARE_VERSION   "v1.0.0-pilot"
#define HARDWARE_MODEL     "ESP32-D4i-Zhaga-Controller"

// ==========================================
// 2. NETWORK & MQTT BROKER CONFIG
// ==========================================
#define WIFI_SSID          "Your_WiFi_SSID"
#define WIFI_PASSWORD      "Your_WiFi_Password"

#define MQTT_BROKER        "broker.emqx.io" // Hoặc IP máy chủ Cloud / LAN
#define MQTT_PORT          1883
#define MQTT_CLIENT_ID     "ESP32_LGT_001"
#define MQTT_USER          ""
#define MQTT_PASS          ""

// MQTT TOPICS (Annex A - Figure 1 & 2)
#define TOPIC_TELEMETRY    "pccom/lighting/" SITE_ID "/" ASSET_ID "/telemetry"
#define TOPIC_HEARTBEAT    "pccom/lighting/" SITE_ID "/" ASSET_ID "/heartbeat"
#define TOPIC_COMMAND      "pccom/lighting/" SITE_ID "/" ASSET_ID "/command"
#define TOPIC_RESULT       "pccom/lighting/" SITE_ID "/" ASSET_ID "/result"

// ==========================================
// 3. HARDWARE PINOUT MAPPING
// ==========================================
#define PIN_PWM_DIMMING    18   // Điều khiển Dimming đèn LED (0 - 100%)
#define PIN_RELAY_POWER    23   // Rơ-le cắt nguồn an toàn độc lập
#define PIN_STATUS_LED     2    // Đèn LED báo trạng thái mạng / lỗi
#define PIN_TEMP_SENSOR    4    // Cảm biến nhiệt độ (DHT22 / DS18B20)
#define PIN_LDR_LUX        34   // Cảm biến quang trở Analog (Hoặc I2C BH1750 SDA 21, SCL 22)

// ==========================================
// 4. TIMING & THRESHOLDS (RFP Section 2 & 7)
// ==========================================
#define TELEMETRY_INTERVAL_MS   60000UL  // 60s chu kỳ gửi telemetry
#define HEARTBEAT_INTERVAL_MS   30000UL  // 30s gửi nhịp tim sống
#define OFFLINE_FALLBACK_SEC    180      // 180s mất mạng -> chuyển fallback nội bộ
#define MAX_TEMPERATURE_DERATE  75.0f    // 75°C tự động giảm công suất bảo vệ
#define MAX_TEMPERATURE_CUTOFF  85.0f    // 85°C ngắt rơ-le khẩn cấp

#endif // CONFIG_H
