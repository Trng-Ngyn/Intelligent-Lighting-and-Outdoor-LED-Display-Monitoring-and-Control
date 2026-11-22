#include "lighting_control/fade_controller.h"
namespace lighting {
ModuleResult FadeController::selectPreset(const DaliDevice& device, uint8_t level,
                                          float current_pct, float target_pct) {
    if (level < 1 || level > 3 || current_pct < 0 || current_pct > 100 ||
        target_pct < 0 || target_pct > 100) {
        return {"FadeController", ModuleStatus::ERROR, "ERROR",
                "INVALID_FADE_REQUEST", "Preset hoặc brightness không hợp lệ",
                static_cast<float>(level), target_pct, false, false};
    }
    const uint8_t settings[] = {0, 5, 6, 7};
    ModuleResult result = dali_.setFadeTime(device, settings[level]);
    if (result.status == ModuleStatus::ERROR) {
        result.module = "FadeController";
        return result;
    }
    ModuleResult target_result = dali_.setBrightness(device, target_pct);
    if (target_result.status == ModuleStatus::ERROR) {
        target_result.module = "FadeController";
        return target_result;
    }
    active_level_ = level;
    return {"FadeController", ModuleStatus::WARNING, "NATIVE_FADE_CONFIGURED",
            "FADE_NOT_VERIFIED", "Driver native fade được cấu hình; chưa đo xác minh",
            current_pct, target_pct, true, true};
}
}  // namespace lighting
