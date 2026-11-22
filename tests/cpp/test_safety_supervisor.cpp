#include <cassert>
#include <cmath>
#include "lighting_control/safety_supervisor.h"
using namespace lighting;
int main() {
    SafetySupervisor supervisor;
    SafetyInput in;
    in.timestamp = "2026-11-20T00:00:00Z";
    in.temperature_sensor_valid = true;
    in.temperature_c = 30;
    in.boot_state_valid = true;
    in.has_requested_brightness = true;
    in.requested_brightness_pct = 80;
    SafetyDecision d = supervisor.evaluate(in);
    assert(d.action == SafetyAction::ALLOW && d.final_brightness_pct == 80);

    in.temperature_sensor_valid = false;
    in.hardware_critical_fault = true;
    in.hardware_fault_code = "POWER_STAGE_FAULT";
    d = supervisor.evaluate(in);
    assert(d.action == SafetyAction::SHUTDOWN && d.final_brightness_pct == 0);

    in.hardware_critical_fault = false;
    in.has_requested_brightness = true;
    in.requested_brightness_pct = 101;
    in.hardware_critical_fault = true;
    d = supervisor.evaluate(in);
    assert(d.action == SafetyAction::SHUTDOWN && d.final_brightness_pct == 0);
    in.hardware_critical_fault = false;
    in.requested_brightness_pct = 80;
    in.has_schedule_brightness = true;
    in.schedule_brightness_pct = 0;
    d = supervisor.evaluate(in);
    assert(d.final_brightness_pct == 0 && d.action == SafetyAction::LIMIT);

    in.temperature_sensor_valid = true;
    in.temperature_c = 80;
    in.has_schedule_brightness = false;
    d = supervisor.evaluate(in);
    assert(std::fabs(d.final_brightness_pct - 64.0f) < 0.01f);

    in.temperature_c = 91;
    d = supervisor.evaluate(in);
    assert(d.action == SafetyAction::SHUTDOWN && d.final_brightness_pct == 0);

    in.temperature_c = 30;
    in.rtc_valid = false;
    in.has_last_valid_brightness = true;
    in.last_valid_brightness_pct = 45;
    d = supervisor.evaluate(in);
    assert(d.action == SafetyAction::HOLD && d.final_brightness_pct == 45);

    in.rtc_valid = true;
    in.temperature_sensor_valid = true;
    in.dali_bus_ok = false;
    d = supervisor.evaluate(in);
    assert(d.action == SafetyAction::HOLD && d.physical_output_state == "UNKNOWN");

    in.dali_bus_ok = true;
    in.ambient_sensor_valid = false;
    in.has_last_valid_brightness = false;
    d = supervisor.evaluate(in);
    assert(d.final_brightness_pct == 0);
    in.ambient_sensor_valid = true;
    in.has_last_valid_brightness = true;
    in.thermal_recovery_pending = true;
    d = supervisor.evaluate(in);
    assert(d.system_state == SystemState::RECOVERY_PENDING && d.final_brightness_pct == 0);
    in.thermal_recovery_pending = false;
    in.command_valid = false;
    d = supervisor.evaluate(in);
    assert(d.action == SafetyAction::REJECT && !d.execution_authorized);
    return 0;
}
