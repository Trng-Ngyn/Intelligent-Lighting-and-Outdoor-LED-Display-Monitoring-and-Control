#ifndef LIGHTING_CONTROL_SAFETY_DECISION_H
#define LIGHTING_CONTROL_SAFETY_DECISION_H

#include <stdint.h>
#include <string>
#include <vector>

namespace lighting {
enum class SafetyAction : uint8_t { ALLOW, LIMIT, HOLD, REJECT, SHUTDOWN };
enum class SystemState : uint8_t {
    INITIALIZING, NORMAL, DERATING, OFFLINE_FALLBACK, DEGRADED,
    THERMAL_SHUTDOWN, FAULT_SHUTDOWN, RECOVERY_PENDING
};

struct FaultInfo {
    std::string fault_code;
    std::string fault_level;
    std::string source_module;
    std::string timestamp;
    std::string description;
    bool recoverable;
    bool active;
};

struct SafetyInput {
    float requested_brightness_pct;
    bool has_requested_brightness;
    float schedule_brightness_pct;
    bool has_schedule_brightness;
    float last_valid_brightness_pct;
    bool has_last_valid_brightness;
    float temperature_c;
    bool temperature_sensor_valid;
    bool thermal_shutdown;
    bool thermal_recovery_pending;
    bool thermal_derating;
    bool hardware_critical_fault;
    std::string hardware_fault_code;
    bool ambient_sensor_valid;
    bool rtc_valid;
    bool mqtt_connected;
    float mqtt_disconnected_seconds;
    bool local_schedule_valid;
    bool command_valid;
    bool replay_detected;
    bool dali_bus_ok;
    bool dali_controller_ok;
    bool fade_controller_ok;
    bool boot_state_valid;
    std::string timestamp;

    SafetyInput();
};

struct SafetyDecision {
    std::string decision_id;
    std::string timestamp;
    SystemState system_state;
    float requested_brightness_pct;
    bool has_requested_brightness;
    float final_brightness_pct;
    SafetyAction action;
    bool execution_authorized;
    std::vector<FaultInfo> active_faults;
    std::vector<std::string> reason_codes;
    std::string physical_output_state;
};

const char* toString(SafetyAction action);
const char* toString(SystemState state);
}  // namespace lighting
#endif
