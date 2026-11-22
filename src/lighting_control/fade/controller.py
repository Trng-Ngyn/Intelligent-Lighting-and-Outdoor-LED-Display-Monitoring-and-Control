"""Preset fade dùng native fade time của driver DALI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from ..contracts import ErrorInfo, ModuleResult, ModuleStatus


@dataclass(frozen=True)
class FadePreset:
    level: int
    label: str
    dali_setting: int
    nominal_seconds: float


DEFAULT_PRESETS = {
    1: FadePreset(1, "Khoảng 3 giây", 5, 2.8),
    2: FadePreset(2, "4 giây", 6, 4.0),
    3: FadePreset(3, "5,7 giây", 7, 5.7),
}


class FadeController:
    def __init__(self, apply_native_fade: Callable[[int], ModuleResult],
                 apply_target_brightness: Callable[[float], ModuleResult],
                 presets: Optional[dict[int, FadePreset]] = None) -> None:
        self.apply_native_fade = apply_native_fade
        self.apply_target_brightness = apply_target_brightness
        self.presets = dict(presets or DEFAULT_PRESETS)
        self.active_preset: Optional[int] = None

    def select_preset(self, level: int, initial_pct: float,
                      target_pct: float) -> ModuleResult:
        data = {"preset_level": level, "initial_brightness_pct": initial_pct,
                "target_brightness_pct": target_pct}
        if level not in self.presets:
            return ModuleResult("FadeController", ModuleStatus.ERROR, "ERROR", data,
                                {}, {}, ErrorInfo("UNKNOWN_FADE_PRESET", "Preset fade không tồn tại", "MEDIUM"))
        if not (0 <= initial_pct <= 100 and 0 <= target_pct <= 100):
            return ModuleResult("FadeController", ModuleStatus.ERROR, "ERROR", data,
                                {}, {}, ErrorInfo("BRIGHTNESS_OUT_OF_RANGE", "Độ sáng phải thuộc [0, 100]%", "HIGH"))
        preset = self.presets[level]
        result = self.apply_native_fade(preset.dali_setting)
        if result.status == ModuleStatus.ERROR:
            return ModuleResult("FadeController", ModuleStatus.ERROR, "NATIVE_FADE_REJECTED",
                                data, {"dali_setting": preset.dali_setting},
                                {"dali_result": result.to_dict()}, result.error)
        target_result = self.apply_target_brightness(target_pct)
        if target_result.status == ModuleStatus.ERROR:
            return ModuleResult("FadeController", ModuleStatus.ERROR, "TARGET_COMMAND_FAILED",
                                data, {"dali_setting": preset.dali_setting},
                                {"fade_result": result.to_dict(),
                                 "target_result": target_result.to_dict()}, target_result.error)
        self.active_preset = level
        warning = ErrorInfo("FADE_NOT_VERIFIED", "Đã cấu hình native fade; chưa đo xác minh thời gian fade thực tế", "LOW")
        return ModuleResult("FadeController", ModuleStatus.WARNING, "NATIVE_FADE_CONFIGURED",
                            data, {"dali_setting": preset.dali_setting,
                                   "nominal_duration_seconds": preset.nominal_seconds,
                                   "label": preset.label,
                                   "target_brightness_pct": target_pct},
                            {"fade_execution": "DRIVER_NATIVE", "software_pwm_fade": False,
                             "target_command_sent": True, "target_command_result": target_result.to_dict(),
                             "elapsed_seconds": None, "progress_pct": None}, warning)
