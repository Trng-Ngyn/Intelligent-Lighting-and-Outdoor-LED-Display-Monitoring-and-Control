#ifndef LIGHTING_CONTROL_SAFETY_SUPERVISOR_H
#define LIGHTING_CONTROL_SAFETY_SUPERVISOR_H
#include <stdint.h>
#include "lighting_control/fault_manager.h"

namespace lighting {
class SafetySupervisor {
public:
    explicit SafetySupervisor(float temperature_sensor_fault_brightness_pct = 30.0f,
                              float mqtt_timeout_seconds = 300.0f);
    SafetyDecision evaluate(const SafetyInput& input);
    const FaultManager& faultManager() const { return fault_manager_; }
private:
    float temperature_sensor_fault_brightness_pct_;
    float mqtt_timeout_seconds_;
    uint32_t decision_counter_;
    FaultManager fault_manager_;
    void collectFaults(const SafetyInput& input);
};
}  // namespace lighting
#endif
