#ifndef LIGHTING_CONTROL_FADE_CONTROLLER_H
#define LIGHTING_CONTROL_FADE_CONTROLLER_H
#include <Arduino.h>
#include "dali_controller.h"
namespace lighting {
struct FadePreset { uint8_t level; uint8_t dali_setting; float nominal_seconds; };
class FadeController {
public:
    explicit FadeController(DaliDimmingController& dali) : dali_(dali), active_level_(0) {}
    ModuleResult selectPreset(const DaliDevice& device, uint8_t level,
                              float current_pct, float target_pct);
    uint8_t activePreset() const { return active_level_; }
private:
    DaliDimmingController& dali_;
    uint8_t active_level_;
};
}  // namespace lighting
#endif
