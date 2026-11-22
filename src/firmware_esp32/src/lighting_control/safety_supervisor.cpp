#include "lighting_control/safety_supervisor.h"
#include <algorithm>
#include <sstream>

namespace lighting {
SafetyInput::SafetyInput()
    : requested_brightness_pct(0), has_requested_brightness(false),
      schedule_brightness_pct(0), has_schedule_brightness(false),
      last_valid_brightness_pct(0), has_last_valid_brightness(false),
      temperature_c(0), temperature_sensor_valid(false), thermal_shutdown(false), thermal_recovery_pending(false),
      thermal_derating(false),
      hardware_critical_fault(false), ambient_sensor_valid(true), rtc_valid(true),
      mqtt_connected(true), mqtt_disconnected_seconds(0), local_schedule_valid(true),
      command_valid(true), replay_detected(false), dali_bus_ok(true), dali_controller_ok(true),
      fade_controller_ok(true), boot_state_valid(false), timestamp("") {}

const char* toString(SafetyAction action) {
    switch (action) {
        case SafetyAction::ALLOW: return "ALLOW";
        case SafetyAction::LIMIT: return "LIMIT";
        case SafetyAction::HOLD: return "HOLD";
        case SafetyAction::REJECT: return "REJECT";
        case SafetyAction::SHUTDOWN: return "SHUTDOWN";
    }
    return "REJECT";
}
const char* toString(SystemState state) {
    switch (state) {
        case SystemState::INITIALIZING: return "INITIALIZING";
        case SystemState::NORMAL: return "NORMAL";
        case SystemState::DERATING: return "DERATING";
        case SystemState::OFFLINE_FALLBACK: return "OFFLINE_FALLBACK";
        case SystemState::DEGRADED: return "DEGRADED";
        case SystemState::THERMAL_SHUTDOWN: return "THERMAL_SHUTDOWN";
        case SystemState::FAULT_SHUTDOWN: return "FAULT_SHUTDOWN";
        case SystemState::RECOVERY_PENDING: return "RECOVERY_PENDING";
    }
    return "DEGRADED";
}

SafetySupervisor::SafetySupervisor(float sensor_fallback, float mqtt_timeout)
    : temperature_sensor_fault_brightness_pct_(sensor_fallback >= 0.0f && sensor_fallback <= 100.0f ? sensor_fallback : 30.0f),
      mqtt_timeout_seconds_(mqtt_timeout > 0.0f ? mqtt_timeout : 300.0f), decision_counter_(0) {}

void SafetySupervisor::collectFaults(const SafetyInput& in) {
    fault_manager_.clear();
    if (in.hardware_critical_fault)
        fault_manager_.raise(in.hardware_fault_code.empty() ? "HARDWARE_CRITICAL_FAULT" : in.hardware_fault_code,
                             "CRITICAL", "Hardware", "Lỗi phần cứng nghiêm trọng", false, in.timestamp);
    if (in.thermal_shutdown || in.thermal_recovery_pending || (in.temperature_sensor_valid && in.temperature_c > 90.0f))
        fault_manager_.raise("THERMAL_SHUTDOWN", "CRITICAL", "ThermalEngine",
                             "Nhiệt độ vượt ngưỡng shutdown", false, in.timestamp);
    if (!in.temperature_sensor_valid)
        fault_manager_.raise("TEMPERATURE_SENSOR_FAULT", "CRITICAL", "ThermalEngine",
                             "Cảm biến nhiệt độ không hợp lệ", true, in.timestamp);
    if (!in.ambient_sensor_valid)
        fault_manager_.raise("AMBIENT_SENSOR_FAULT", "HIGH", "AmbientLightMonitor",
                             "Cảm biến ánh sáng không hợp lệ", true, in.timestamp);
    if (!in.rtc_valid)
        fault_manager_.raise("RTC_INVALID", "CRITICAL", "Clock", "Thời gian không hợp lệ", true, in.timestamp);
    if (!in.mqtt_connected && in.mqtt_disconnected_seconds > mqtt_timeout_seconds_)
        fault_manager_.raise("MQTT_OFFLINE", "WARNING", "MQTT", "Mất MQTT quá timeout", true, in.timestamp);
    if (!in.command_valid)
        fault_manager_.raise("INVALID_COMMAND", "HIGH", "CommandValidator", "Lệnh không hợp lệ", false, in.timestamp);
    if (in.replay_detected)
        fault_manager_.raise("COMMAND_REPLAY", "HIGH", "CommandValidator", "Phát hiện replay", false, in.timestamp);
    if (!in.dali_bus_ok)
        fault_manager_.raise("DALI_BUS_FAULT", "CRITICAL", "DaliController", "Bus DALI lỗi", true, in.timestamp);
    if (!in.fade_controller_ok)
        fault_manager_.raise("FADE_CONTROLLER_FAULT", "ERROR", "FadeController", "Fade controller lỗi", true, in.timestamp);
}

SafetyDecision SafetySupervisor::evaluate(const SafetyInput& in) {
    collectFaults(in);
    SafetyDecision out;
    std::ostringstream id;
    id << "safety-" << ++decision_counter_;
    out.decision_id = id.str();
    out.timestamp = in.timestamp;
    out.system_state = SystemState::NORMAL;
    out.requested_brightness_pct = in.requested_brightness_pct;
    out.has_requested_brightness = in.has_requested_brightness;
    out.final_brightness_pct = 0;
    out.action = SafetyAction::HOLD;
    out.execution_authorized = false;
    out.active_faults = fault_manager_.activeFaults();
    out.physical_output_state = in.dali_bus_ok ? "NOT_VERIFIED" : "UNKNOWN";

    const float last = in.has_last_valid_brightness
        ? std::max(0.0f, std::min(100.0f, in.last_valid_brightness_pct)) : 0.0f;
    if (in.hardware_critical_fault) {
        out.system_state = SystemState::FAULT_SHUTDOWN;
        out.final_brightness_pct = 0;
        out.action = SafetyAction::SHUTDOWN;
        out.execution_authorized = true;
        out.reason_codes.push_back("HARDWARE_CRITICAL_FAULT");
        return out;
    }
    if (in.thermal_shutdown || in.thermal_recovery_pending || (in.temperature_sensor_valid && in.temperature_c > 90.0f)) {
        out.system_state = in.thermal_recovery_pending ? SystemState::RECOVERY_PENDING : SystemState::THERMAL_SHUTDOWN;
        out.final_brightness_pct = 0;
        out.action = SafetyAction::SHUTDOWN;
        out.execution_authorized = true;
        out.reason_codes.push_back(in.thermal_recovery_pending ? "THERMAL_RECOVERY_PENDING" : "THERMAL_SHUTDOWN");
        return out;
    }
    if (in.has_requested_brightness &&
        (in.requested_brightness_pct < 0 || in.requested_brightness_pct > 100)) {
        out.system_state = SystemState::DEGRADED;
        out.final_brightness_pct = last;
        out.action = SafetyAction::REJECT;
        out.reason_codes.push_back("BRIGHTNESS_OUT_OF_RANGE");
        return out;
    }
    if (!in.command_valid || in.replay_detected) {
        out.system_state = SystemState::DEGRADED;
        out.final_brightness_pct = last;
        out.action = SafetyAction::REJECT;
        out.reason_codes.push_back(in.replay_detected ? "COMMAND_REPLAY_REJECTED" : "INVALID_COMMAND_REJECTED");
        return out;
    }
    if (!in.boot_state_valid && !in.has_last_valid_brightness) {
        out.system_state = SystemState::INITIALIZING;
        out.final_brightness_pct = 0;
        out.action = SafetyAction::SHUTDOWN;
        out.execution_authorized = true;
        out.reason_codes.push_back("NO_VALID_STORED_OUTPUT_STATE");
        return out;
    }
    if (!in.dali_bus_ok) {
        out.system_state = SystemState::DEGRADED;
        out.final_brightness_pct = last;
        out.action = SafetyAction::HOLD;
        out.reason_codes.push_back("DALI_BUS_FAULT");
        out.reason_codes.push_back("PHYSICAL_OUTPUT_UNKNOWN");
        return out;
    }
    if (!in.dali_controller_ok) {
        out.system_state = SystemState::DEGRADED;
        out.final_brightness_pct = last;
        out.action = SafetyAction::HOLD;
        out.reason_codes.push_back("DALI_CONTROLLER_ERROR");
        return out;
    }
    if (!in.rtc_valid) {
        out.system_state = SystemState::DEGRADED;
        out.final_brightness_pct = last;
        out.action = SafetyAction::HOLD;
        out.reason_codes.push_back("RTC_INVALID");
        if (!in.temperature_sensor_valid) {
            out.final_brightness_pct = std::min(out.final_brightness_pct, temperature_sensor_fault_brightness_pct_);
            out.reason_codes.push_back("TEMPERATURE_SENSOR_FAULT_FIXED_30_CAP");
        } else if (in.thermal_derating || (in.temperature_c > 75.0f && in.temperature_c <= 90.0f)) {
            out.final_brightness_pct *= 0.8f;
            out.reason_codes.push_back("THERMAL_DERATING_0_8");
        }
        return out;
    }
    if (!in.fade_controller_ok) {
        out.system_state = SystemState::DEGRADED;
        out.final_brightness_pct = last;
        out.action = SafetyAction::HOLD;
        out.reason_codes.push_back("FADE_CONTROLLER_FAULT");
        return out;
    }
    const bool offline = !in.mqtt_connected && in.mqtt_disconnected_seconds > mqtt_timeout_seconds_;
    if (offline && !in.local_schedule_valid) {
        out.system_state = SystemState::DEGRADED;
        out.final_brightness_pct = last;
        out.action = SafetyAction::HOLD;
        out.reason_codes.push_back("OFFLINE_WITHOUT_VALID_SCHEDULE");
        return out;
    }

    float base = in.has_requested_brightness ? in.requested_brightness_pct : last;
    if (offline) {
        base = in.has_schedule_brightness ? in.schedule_brightness_pct : 0;
        out.reason_codes.push_back("MQTT_OFFLINE_LOCAL_SCHEDULE");
    } else if (in.has_schedule_brightness) {
        if (in.schedule_brightness_pct < base) {
            base = in.schedule_brightness_pct;
            out.reason_codes.push_back("SCHEDULE_BRIGHTNESS_CAP");
        }
    }
    if (!in.ambient_sensor_valid) {
        if (in.has_last_valid_brightness) base = std::min(base, last);
        else base = 0.0f;
        out.reason_codes.push_back("AMBIENT_SENSOR_FAULT_HOLD");
    }
    if (!in.temperature_sensor_valid) {
        base = std::min(base, temperature_sensor_fault_brightness_pct_);
        out.reason_codes.push_back("TEMPERATURE_SENSOR_FAULT_FIXED_30_CAP");
        out.system_state = SystemState::DEGRADED;
    }
    if (in.thermal_derating || (in.temperature_sensor_valid && in.temperature_c > 75.0f && in.temperature_c <= 90.0f)) {
        base *= 0.8f;
        out.reason_codes.push_back("THERMAL_DERATING_0_8");
        out.system_state = SystemState::DERATING;
    }
    if (offline) out.system_state = SystemState::OFFLINE_FALLBACK;
    if (out.reason_codes.empty()) out.reason_codes.push_back("NO_ACTIVE_FAULT");
    out.final_brightness_pct = std::max(0.0f, std::min(100.0f, base));
    out.action = out.reason_codes.size() == 1 && out.reason_codes[0] == "NO_ACTIVE_FAULT"
        ? SafetyAction::ALLOW : SafetyAction::LIMIT;
    if (in.has_last_valid_brightness && (!in.temperature_sensor_valid || !in.ambient_sensor_valid) && out.final_brightness_pct == last)
        out.action = SafetyAction::HOLD;
    out.execution_authorized = true;
    return out;
}
}  // namespace lighting
