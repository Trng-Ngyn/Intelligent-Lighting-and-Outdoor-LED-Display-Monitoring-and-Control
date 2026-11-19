#ifndef LIGHTING_CONTROL_THERMAL_ENGINE_H
#define LIGHTING_CONTROL_THERMAL_ENGINE_H
#include <Arduino.h>
#include "module_result.h"
namespace lighting {
enum class ThermalState : uint8_t { NORMAL, DERATING, SHUTDOWN, SENSOR_FAULT };
class ThermalDeratingEngine {
public:
    ThermalDeratingEngine(float derate_c = 75.0f, float shutdown_c = 90.0f,
                          float factor = 0.8f, uint32_t recovery_ms = 300000UL);
    ModuleResult evaluate(float temperature_c, bool sensor_valid,
                          float requested_pct, uint32_t now_ms);
    ThermalState state() const { return state_; }
private:
    float derate_c_, shutdown_c_, factor_;
    uint32_t recovery_ms_, below_since_ms_;
    bool recovery_timer_active_, shutdown_latched_;
    ThermalState state_;
};
}  // namespace lighting
#endif
