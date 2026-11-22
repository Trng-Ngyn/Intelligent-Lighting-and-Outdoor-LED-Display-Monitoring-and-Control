#include "lighting_control/thermal_engine.h"
namespace lighting {
ThermalDeratingEngine::ThermalDeratingEngine(float derate_c, float shutdown_c,
                                             float factor, uint32_t recovery_ms)
    : derate_c_(derate_c), shutdown_c_(shutdown_c), factor_(factor),
      recovery_ms_(recovery_ms), below_since_ms_(0), recovery_timer_active_(false),
      shutdown_latched_(false), state_(ThermalState::NORMAL) {}

ModuleResult ThermalDeratingEngine::evaluate(float temperature_c, bool sensor_valid,
                                              float requested_pct, uint32_t now_ms) {
    if (requested_pct < 0 || requested_pct > 100) {
        return {"ThermalDeratingEngine", ModuleStatus::ERROR, "ERROR",
                "BRIGHTNESS_OUT_OF_RANGE", "Brightness yêu cầu ngoài [0,100]%",
                requested_pct, 0, false, false};
    }
    if (!sensor_valid || isnan(temperature_c)) {
        state_ = ThermalState::SENSOR_FAULT;
        recovery_timer_active_ = false;
        return {"ThermalDeratingEngine", ModuleStatus::ERROR, "SENSOR_FAULT",
                "TEMPERATURE_SENSOR_FAULT", "Không có số đo nhiệt độ hợp lệ; chuyển Safety Supervisor",
                temperature_c, 0, false, false, "CRITICAL", "temperature sensor invalid; defer to Safety Supervisor"};
    }
    if (temperature_c > shutdown_c_) {
        shutdown_latched_ = true;
        recovery_timer_active_ = false;
        state_ = ThermalState::SHUTDOWN;
        return {"ThermalDeratingEngine", ModuleStatus::ERROR, "SHUTDOWN",
                "THERMAL_SHUTDOWN", "Nhiệt độ vượt 90°C; yêu cầu ngắt nguồn",
                temperature_c, 0, true, false, "CRITICAL", "independent relay shutdown required"};
    }
    if (temperature_c >= derate_c_) {
        recovery_timer_active_ = false; // >=75°C reset bộ đếm hồi phục
        if (shutdown_latched_) {
            state_ = ThermalState::SHUTDOWN;
            return {"ThermalDeratingEngine", ModuleStatus::ERROR, "SHUTDOWN",
                    "THERMAL_RECOVERY_PENDING", "Chờ dưới 75°C liên tục 300 giây",
                    temperature_c, 0, true, true};
        }
        if (temperature_c > derate_c_) {
            state_ = ThermalState::DERATING;
            return {"ThermalDeratingEngine", ModuleStatus::WARNING, "DERATING",
                    "", "", temperature_c, requested_pct * factor_, true, true};
        }
        state_ = ThermalState::NORMAL; // bằng đúng 75°C chưa vượt ngưỡng derate
        return {"ThermalDeratingEngine", ModuleStatus::SUCCESS, "NORMAL", "", "",
                temperature_c, requested_pct, true, true};
    }
    if (!recovery_timer_active_) {
        below_since_ms_ = now_ms;
        recovery_timer_active_ = true;
    }
    const uint32_t elapsed = now_ms - below_since_ms_;
    if (shutdown_latched_ && elapsed < recovery_ms_) {
        state_ = ThermalState::SHUTDOWN;
        return {"ThermalDeratingEngine", ModuleStatus::ERROR, "SHUTDOWN",
                "THERMAL_RECOVERY_PENDING", "Đang chờ đủ 300 giây dưới 75°C",
                temperature_c, 0, true, true};
    }
    shutdown_latched_ = false;
    state_ = ThermalState::NORMAL;
    return {"ThermalDeratingEngine", ModuleStatus::SUCCESS, "NORMAL", "", "",
            temperature_c, requested_pct, true, true};
}
}  // namespace lighting
