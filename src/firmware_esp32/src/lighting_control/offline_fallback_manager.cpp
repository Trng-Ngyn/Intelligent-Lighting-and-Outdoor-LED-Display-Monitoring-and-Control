#include "lighting_control/offline_fallback_manager.h"
namespace lighting {
OfflineFallbackManager::OfflineFallbackManager(uint32_t timeout_ms, float dark_lux,
                                               float bright_lux, uint32_t stable_ms)
    : timeout_ms_(timeout_ms), stable_ms_(stable_ms), dark_since_ms_(0),
      bright_since_ms_(0), dark_lux_(dark_lux), bright_lux_(bright_lux),
      dark_timer_active_(false), bright_timer_active_(false),
      dawn_dark_known_(false), dawn_is_dark_(false), last_target_pct_(40),
      has_last_target_(false) {}

void OfflineFallbackManager::resetDawnTimers() {
    dark_timer_active_ = false;
    bright_timer_active_ = false;
}

ModuleResult OfflineFallbackManager::evaluate(bool mqtt_connected,
                                               uint32_t disconnected_ms,
                                               const LocalClock& clock,
                                               const AmbientSample& ambient,
                                               uint32_t now_ms) {
    if (mqtt_connected) {
        resetDawnTimers();
        return {"OfflineFallbackManager", ModuleStatus::SUCCESS, "ONLINE", "", "",
                disconnected_ms / 1000.0f, 0, false, true};
    }
    if (disconnected_ms <= timeout_ms_) {
        return {"OfflineFallbackManager", ModuleStatus::SUCCESS, "WAITING_TIMEOUT", "", "",
                disconnected_ms / 1000.0f, 0, false, true};
    }
    if (!clock.valid || clock.hour > 23 || clock.minute > 59) {
        return {"OfflineFallbackManager", ModuleStatus::ERROR, "CLOCK_FAULT",
                "RTC_INVALID", "Không có giờ hợp lệ; Safety Supervisor quyết định safe policy",
                0, 0, false, false, "CRITICAL", "RTC invalid; defer to Safety Supervisor"};
    }

    const uint16_t minute = static_cast<uint16_t>(clock.hour) * 60 + clock.minute;
    int target = 0;
    if (minute >= 18 * 60 && minute < 22 * 60) target = 100;
    else if (minute >= 22 * 60) target = 70;
    else if (minute < 5 * 60) target = 40;

    if (minute >= 5 * 60 && minute < 5 * 60 + 30) {
        if (!ambient.valid || isnan(ambient.lux)) {
            resetDawnTimers();
            target = has_last_target_ ? last_target_pct_ : 40;
            return {"OfflineFallbackManager", ModuleStatus::WARNING, "SENSOR_FAULT",
                    "AMBIENT_SENSOR_FAULT", "Lỗi lux: giữ mức đã biết/lịch 40%, không coi lỗi là 0 lux",
                    ambient.lux, static_cast<float>(target), true, true};
        }
        if (ambient.lux <= dark_lux_) {
            bright_timer_active_ = false;
            if (!dark_timer_active_) { dark_since_ms_ = now_ms; dark_timer_active_ = true; }
            if (now_ms - dark_since_ms_ >= stable_ms_) { dawn_dark_known_ = true; dawn_is_dark_ = true; }
            target = (dawn_dark_known_ && dawn_is_dark_) ? 40 : (has_last_target_ ? last_target_pct_ : 40);
        } else if (ambient.lux >= bright_lux_) {
            dark_timer_active_ = false;
            if (!bright_timer_active_) { bright_since_ms_ = now_ms; bright_timer_active_ = true; }
            if (now_ms - bright_since_ms_ >= stable_ms_) { dawn_dark_known_ = true; dawn_is_dark_ = false; }
            target = (dawn_dark_known_ && !dawn_is_dark_) ? 0 : (has_last_target_ ? last_target_pct_ : 40);
        } else {
            resetDawnTimers();
            target = has_last_target_ ? last_target_pct_ : 40;
        }
    } else {
        resetDawnTimers();
    }
    last_target_pct_ = target;
    has_last_target_ = true;
    return {"OfflineFallbackManager", ModuleStatus::SUCCESS, "LOCAL_SCHEDULE", "", "",
            disconnected_ms / 1000.0f, static_cast<float>(target), true, true};
}
}  // namespace lighting
