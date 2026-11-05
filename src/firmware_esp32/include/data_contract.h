#ifndef DATA_CONTRACT_H
#define DATA_CONTRACT_H

#include <Arduino.h>

// Tuân thủ Annex C: Data contracts and quality (DAT 01)
struct TelemetryPayload {
    const char* schema_version = "1.0.0";
    char message_id[37];
    const char* asset_id;
    uint32_t sequence;
    unsigned long source_time; // UTC Epoch
    
    // Đơn vị tiêu chuẩn: W, Wh, V, A, °C, lx
    float power_w;
    float energy_wh;
    float voltage_v;
    float current_a;
    float power_factor;
    float temperature_c;
    float ambient_lux;
    
    uint8_t brightness_pct;
    bool relay_state;
    const char* quality; // "GOOD", "ESTIMATED", "DEGRADED"
};

struct CommandRequest {
    char command_id[37];
    char actor[32];
    char action[16]; // "DIM", "SWITCH", "PROFILE"
    int requested_value; // 0-100%
    char policy_version[16];
    unsigned long issued_at;
    unsigned long expires_at;
    int priority;
};

struct CommandResult {
    const char* command_id;
    const char* asset_id;
    unsigned long device_time;
    const char* status; // "ACKNOWLEDGED", "EXECUTED", "REJECTED", "EXPIRED"
    const char* reason;
    int observed_value;
    const char* evidence_source; // "PWM_FEEDBACK", "RELAY_STATUS"
};

#endif // DATA_CONTRACT_H
