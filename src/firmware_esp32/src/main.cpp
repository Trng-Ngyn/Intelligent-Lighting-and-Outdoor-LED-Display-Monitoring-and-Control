#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <time.h>
#include "config.h"
#include "data_contract.h"

WiFiClient espClient;
PubSubClient mqttClient(espClient);

// Trạng thái vận hành thiết bị
uint8_t current_brightness = 0;       // 0 - 100%
bool is_powered = true;
uint32_t message_sequence = 0;
unsigned long last_telemetry_time = 0;
unsigned long last_heartbeat_time = 0;
unsigned long last_mqtt_message_rx = 0;
bool is_offline_mode = false;
float cumulative_energy_wh = 125.40f; // Năng lượng tích lũy mô phỏng

// NTP Server
const char* ntp_server = "pool.ntp.org";

unsigned long get_current_epoch() {
    time_t now;
    time(&now);
    return (unsigned long)now;
}

void set_hardware_dimming(uint8_t pct) {
    if (pct > 100) pct = 100;
    current_brightness = pct;
    // ESP32 PWM 8-bit: 0 - 255
    uint32_t duty = (pct * 255) / 100;
    ledcWrite(0, duty);
    Serial.printf("[HARDWARE] Dimming LED pin %d to %d%% (Duty: %d)\n", PIN_PWM_DIMMING, pct, duty);
}

void publish_command_result(const char* cmd_id, const char* status, const char* reason, int observed_val) {
    StaticJsonDocument<512> doc;
    doc["command_id"] = cmd_id;
    doc["asset_id"] = ASSET_ID;
    doc["device_time"] = get_current_epoch();
    doc["status"] = status;
    doc["reason"] = reason;
    doc["observed_value"] = observed_val;
    doc["evidence_source"] = "PWM_MEASURED_FEEDBACK";

    char buffer[512];
    serializeJson(doc, buffer);
    mqttClient.publish(TOPIC_RESULT, buffer);
    Serial.printf("[RESULT] -> %s: %s (%s)\n", cmd_id, status, reason);
}

void handle_incoming_command(char* topic, byte* payload, unsigned int length) {
    StaticJsonDocument<1024> doc;
    DeserializationError error = deserializeJson(doc, payload, length);
    if (error) {
        Serial.println("[ERROR] Failed to parse command JSON");
        return;
    }

    last_mqtt_message_rx = millis();
    const char* cmd_id = doc["command_id"] | "CMD_UNKNOWN";
    const char* action = doc["action"] | "NONE";
    int requested_val = doc["requested_value"] | 0;
    unsigned long expires_at = doc["expires_at"] | 0;
    unsigned long now_epoch = get_current_epoch();

    Serial.printf("[COMMAND RX] ID: %s | Action: %s | Val: %d\n", cmd_id, action, requested_val);

    // CTL 01 & 02: Kiem tra han lenh (Replay / Expiry check)
    if (expires_at > 0 && now_epoch > expires_at) {
        publish_command_result(cmd_id, "EXPIRED", "Command arrived after expiration timestamp", current_brightness);
        return;
    }

    // LGT 02: Thuc thi lenh Dimming
    if (strcmp(action, "DIM") == 0) {
        if (requested_val < 0 || requested_val > 100) {
            publish_command_result(cmd_id, "REJECTED", "Brightness out of range [0-100]", current_brightness);
            return;
        }
        set_hardware_dimming((uint8_t)requested_val);
        publish_command_result(cmd_id, "EXECUTED", "Dimming set successfully", current_brightness);
    } 
    // Lenh SWITCH On/Off
    else if (strcmp(action, "SWITCH") == 0) {
        is_powered = (requested_val > 0);
        digitalWrite(PIN_RELAY_POWER, is_powered ? HIGH : LOW);
        if (!is_powered) set_hardware_dimming(0);
        publish_command_result(cmd_id, "EXECUTED", is_powered ? "Relay turned ON" : "Relay turned OFF", is_powered ? 1 : 0);
    } 
    else {
        publish_command_result(cmd_id, "REJECTED", "Unsupported action type", current_brightness);
    }
}

void connect_wifi() {
    Serial.print("[WIFI] Connecting to ");
    Serial.println(WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    int timeout = 20;
    while (WiFi.status() != WL_CONNECTED && timeout > 0) {
        delay(500);
        Serial.print(".");
        timeout--;
    }
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\n[WIFI] Connected! IP: " + WiFi.localIP().toString());
        configTime(7 * 3600, 0, ntp_server); // GMT+7
    } else {
        Serial.println("\n[WARN] WiFi not connected. Running in Standalone Mock mode.");
    }
}

void reconnect_mqtt() {
    if (WiFi.status() != WL_CONNECTED) return;
    if (!mqttClient.connected()) {
        Serial.print("[MQTT] Connecting to broker ");
        Serial.print(MQTT_BROKER);
        if (mqttClient.connect(MQTT_CLIENT_ID, MQTT_USER, MQTT_PASS)) {
            Serial.println(" -> Connected!");
            mqttClient.subscribe(TOPIC_COMMAND);
            digitalWrite(PIN_STATUS_LED, HIGH);
        } else {
            Serial.printf(" -> Failed (rc=%d). Retrying later...\n", mqttClient.state());
            digitalWrite(PIN_STATUS_LED, LOW);
        }
    }
}

void send_telemetry() {
    message_sequence++;
    
    // Mo phong doc cam bien (W, V, A, lux, °C)
    float simulated_v = 220.5f + ((float)(random(-15, 15)) / 10.0f);
    float simulated_a = (current_brightness > 0) ? (0.45f * (current_brightness / 100.0f)) : 0.02f;
    float simulated_w = simulated_v * simulated_a * 0.95f; // Power factor ~0.95
    cumulative_energy_wh += (simulated_w * (TELEMETRY_INTERVAL_MS / 3600000.0f));
    
    // Doc cam bien quang tro ADC LDR (GPIO 34)
    int raw_ldr = analogRead(PIN_LDR_LUX);
    float ambient_lux = map(raw_ldr, 0, 4095, 0, 1000); // 0 - 1000 lux
    float temp_c = 36.5f + (float)random(-5, 15) / 10.0f;

    // LGT 06: Kiem tra bao ve qua nhiet (Thermal derating)
    if (temp_c >= MAX_TEMPERATURE_CUTOFF) {
        Serial.println("[CRITICAL] Temperature exceeded cutoff! Tripping relay!");
        digitalWrite(PIN_RELAY_POWER, LOW);
        is_powered = false;
        set_hardware_dimming(0);
    } else if (temp_c >= MAX_TEMPERATURE_DERATE && current_brightness > 40) {
        Serial.println("[WARN] High temperature! Derating brightness to 40%");
        set_hardware_dimming(40);
    }

    // Dong goi ban tin JSON chuan Annex C (DAT 01)
    StaticJsonDocument<1024> doc;
    doc["schema_version"] = "1.0.0";
    doc["message_id"] = "MSG_" + String(millis()) + "_" + String(random(1000, 9999));
    doc["asset_id"] = ASSET_ID;
    doc["sequence"] = message_sequence;
    doc["source_time"] = get_current_epoch();

    JsonObject metrics = doc.createNestedObject("metrics");
    metrics["power_w"] = serialized(String(simulated_w, 2));
    metrics["energy_wh"] = serialized(String(cumulative_energy_wh, 2));
    metrics["voltage_v"] = serialized(String(simulated_v, 1));
    metrics["current_a"] = serialized(String(simulated_a, 3));
    metrics["power_factor"] = 0.95;
    metrics["temperature_c"] = serialized(String(temp_c, 1));
    metrics["ambient_lux"] = serialized(String(ambient_lux, 1));

    doc["brightness_pct"] = current_brightness;
    doc["relay_state"] = is_powered;
    doc["quality"] = "GOOD";

    char buffer[1024];
    serializeJson(doc, buffer);
    mqttClient.publish(TOPIC_TELEMETRY, buffer);
    Serial.printf("[TELEMETRY #%d] Sent: %dW | %dV | %dA | %dlux | %d%% Brightness\n", 
                  message_sequence, (int)simulated_w, (int)simulated_v, (int)simulated_a, (int)ambient_lux, current_brightness);
}

void check_offline_fallback() {
    // OPS 02 & CTL 04: Chế độ tự hành khi mất mạng quá ngưỡng cho phép
    if (millis() - last_mqtt_message_rx > (OFFLINE_FALLBACK_SEC * 1000UL)) {
        if (!is_offline_mode) {
            Serial.println("[FALLBACK] Cloud connection lost! Activating local fallback policy.");
            is_offline_mode = true;
        }
        // Thuat toan thich ung cuc bo theo lux: Troi toi (< 50 lux) -> bat 80%, troi sang (> 300 lux) -> giam 10%
        int raw_ldr = analogRead(PIN_LDR_LUX);
        float lux = map(raw_ldr, 0, 4095, 0, 1000);
        if (lux < 50 && current_brightness < 80) {
            set_hardware_dimming(80);
        } else if (lux > 300 && current_brightness > 10) {
            set_hardware_dimming(10);
        }
    } else {
        is_offline_mode = false;
    }
}

void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.println("\n=======================================================");
    Serial.println("  PCCOM INTELLIGENT LIGHTING CONTROLLER - ESP32 FIRMWARE");
    Serial.printf("  Asset ID: %s | Model: %s\n", ASSET_ID, HARDWARE_MODEL);
    Serial.println("=======================================================");

    pinMode(PIN_RELAY_POWER, OUTPUT);
    digitalWrite(PIN_RELAY_POWER, HIGH); // Bat relay cap nguon mac dinh
    pinMode(PIN_STATUS_LED, OUTPUT);
    pinMode(PIN_LDR_LUX, INPUT);

    // Cau hinh LEDC PWM tren ESP32 (Kenh 0, Tan so 5000Hz, Do phan giai 8-bit)
    ledcSetup(0, 5000, 8);
    ledcAttachPin(PIN_PWM_DIMMING, 0);
    set_hardware_dimming(50); // Khoi dong mac dinh 50%

    connect_wifi();
    mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
    mqttClient.setCallback(handle_incoming_command);
    mqttClient.setBufferSize(1024);

    last_mqtt_message_rx = millis();
}

void loop() {
    if (!mqttClient.connected()) {
        reconnect_mqtt();
    } else {
        mqttClient.loop();
    }

    unsigned long now = millis();
    // Chu ky telemetry 60s
    if (now - last_telemetry_time >= TELEMETRY_INTERVAL_MS) {
        last_telemetry_time = now;
        send_telemetry();
    }

    // Kiem tra fallback an toan khi mat cloud
    check_offline_fallback();

    delay(10);
}
