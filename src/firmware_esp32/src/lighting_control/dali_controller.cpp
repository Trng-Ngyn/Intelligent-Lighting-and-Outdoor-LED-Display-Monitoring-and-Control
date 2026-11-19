#include "lighting_control/dali_controller.h"

namespace lighting {
DaliDimmingController::DaliDimmingController(IDaliBus& bus,
                                             const IArcPowerMapper& mapper)
    : bus_(bus), mapper_(mapper) {}

ModuleResult DaliDimmingController::setBrightness(const DaliDevice& device,
                                                   float brightness_pct) {
    if (brightness_pct < 0.0f || brightness_pct > 100.0f) {
        return {"DaliDimmingController", ModuleStatus::ERROR, "ERROR",
                "BRIGHTNESS_OUT_OF_RANGE", "Brightness phải thuộc [0,100]%",
                brightness_pct, 0, false, false};
    }
    uint8_t arc_level = 0;
    if (brightness_pct > 0.0f &&
        !mapper_.map(brightness_pct, device, arc_level)) {
        return {"DaliDimmingController", ModuleStatus::ERROR, "ERROR",
                "ARC_POWER_MAPPING_FAILED", "Không chuyển được brightness sang arc-power",
                brightness_pct, 0, false, true};
    }
    if (brightness_pct > 0.0f &&
        (arc_level < device.min_level || arc_level > device.max_level)) {
        return {"DaliDimmingController", ModuleStatus::ERROR, "ERROR",
                "ARC_POWER_OUT_OF_RANGE", "Arc-power vượt giới hạn driver",
                brightness_pct, static_cast<float>(arc_level), false, false};
    }
    if (!bus_.sendArcPower(device.address, arc_level)) {
        return {"DaliDimmingController", ModuleStatus::ERROR, "BUS_ERROR",
                "DALI_BUS_SEND_FAILED", "Bus DALI không gửi được frame",
                brightness_pct, static_cast<float>(arc_level), false, true};
    }
    return {"DaliDimmingController", ModuleStatus::WARNING, "UNVERIFIED",
            "OUTPUT_UNVERIFIED", "Đã gửi lệnh; chưa xác minh ánh sáng vật lý",
            brightness_pct, static_cast<float>(arc_level), true, true};
}

ModuleResult DaliDimmingController::setFadeTime(const DaliDevice& device,
                                                 uint8_t setting) {
    if (setting < 1 || setting > 15) {
        return {"DaliDimmingController", ModuleStatus::ERROR, "ERROR",
                "FADE_SETTING_OUT_OF_RANGE", "Fade setting phải thuộc [1,15]",
                static_cast<float>(setting), 0, false, false};
    }
    if (!bus_.setFadeTime(device.address, setting)) {
        return {"DaliDimmingController", ModuleStatus::ERROR, "BUS_ERROR",
                "DALI_BUS_SEND_FAILED", "Không gửi được cấu hình native fade",
                static_cast<float>(setting), 0, false, true};
    }
    return {"DaliDimmingController", ModuleStatus::WARNING, "FADE_CONFIGURED",
            "FADE_UNVERIFIED", "Đã cấu hình native fade; chưa xác minh thời gian thực tế",
            static_cast<float>(setting), static_cast<float>(setting), true, true};
}
}  // namespace lighting
