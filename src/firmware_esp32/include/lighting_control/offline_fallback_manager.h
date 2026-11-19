#ifndef LIGHTING_CONTROL_OFFLINE_FALLBACK_MANAGER_H
#define LIGHTING_CONTROL_OFFLINE_FALLBACK_MANAGER_H
#include <Arduino.h>
#include "module_result.h"
namespace lighting {
struct LocalClock { uint8_t hour; uint8_t minute; bool valid; };
struct AmbientSample { float lux; bool valid; };
class OfflineFallbackManager {
public:
    OfflineFallbackManager(uint32_t mqtt_timeout_ms = 300000UL,
                           float dark_lux = 50.0f, float bright_lux = 80.0f,
                           uint32_t stable_ms = 120000UL);
    ModuleResult evaluate(bool mqtt_connected, uint32_t disconnected_ms,
                          const LocalClock& clock, const AmbientSample& ambient,
                          uint32_t now_ms);
private:
    uint32_t timeout_ms_, stable_ms_, dark_since_ms_, bright_since_ms_;
    float dark_lux_, bright_lux_;
    bool dark_timer_active_, bright_timer_active_, dawn_dark_known_, dawn_is_dark_;
    int last_target_pct_;
    bool has_last_target_;
    void resetDawnTimers();
};
}  // namespace lighting
#endif
