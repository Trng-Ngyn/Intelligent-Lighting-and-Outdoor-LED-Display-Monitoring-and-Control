"""Bảo vệ nhiệt: derate theo hệ số từ brightness gốc và shutdown có hysteresis."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from ..contracts import ErrorInfo, ModuleResult, ModuleStatus


class ThermalState(str, Enum):
    NORMAL = "NORMAL"
    DERATING = "DERATING"
    SHUTDOWN = "SHUTDOWN"
    SENSOR_FAULT = "SENSOR_FAULT"


class ThermalDeratingEngine:
    def __init__(self, derate_threshold_c: float = 75.0,
                 shutdown_threshold_c: float = 90.0,
                 derate_factor: float = 0.8,
                 recovery_seconds: float = 300.0) -> None:
        if not (0 < derate_threshold_c < shutdown_threshold_c):
            raise ValueError("Ngưỡng nhiệt không hợp lệ")
        if not 0 < derate_factor <= 1 or recovery_seconds < 0:
            raise ValueError("Hệ số derate/recovery không hợp lệ")
        self.derate_threshold_c = derate_threshold_c
        self.shutdown_threshold_c = shutdown_threshold_c
        self.derate_factor = derate_factor
        self.recovery_seconds = recovery_seconds
        self.state = ThermalState.NORMAL
        self._below_threshold_since: Optional[float] = None
        self._shutdown_latched = False

    def evaluate(self, temperature_c: Optional[float], requested_brightness_pct: float,
                 now_seconds: float, sensor_valid: bool = True) -> ModuleResult:
        data = {"temperature_c": temperature_c,
                "requested_brightness_pct": requested_brightness_pct,
                "sensor_valid": sensor_valid, "now_seconds": now_seconds}
        if not 0 <= requested_brightness_pct <= 100:
            return self._error("BRIGHTNESS_OUT_OF_RANGE", "Độ sáng yêu cầu phải thuộc [0, 100]%", data)
        if not sensor_valid or temperature_c is None:
            self.state = ThermalState.SENSOR_FAULT
            self._below_threshold_since = None
            return ModuleResult("ThermalDeratingEngine", ModuleStatus.ERROR,
                                self.state.value, data,
                                {"final_brightness_pct": None, "shutdown_required": True,
                                 "derating_factor": None},
                                {"policy": "DEFER_TO_SAFETY_SUPERVISOR"},
                                ErrorInfo("TEMPERATURE_SENSOR_FAULT",
                                          "Không có số đo nhiệt độ hợp lệ; không tự giả định nhiệt độ an toàn", "CRITICAL", False))
        if temperature_c > self.shutdown_threshold_c:
            self._shutdown_latched = True
            self._below_threshold_since = None
            self.state = ThermalState.SHUTDOWN
            return ModuleResult("ThermalDeratingEngine", ModuleStatus.ERROR,
                                self.state.value, data,
                                {"final_brightness_pct": 0.0, "shutdown_required": True,
                                 "derating_factor": 0.0},
                                {"reason": "TEMPERATURE_ABOVE_SHUTDOWN_THRESHOLD"},
                                ErrorInfo("THERMAL_SHUTDOWN", "Nhiệt độ vượt 90°C; yêu cầu ngắt độc lập", "CRITICAL", False))

        if temperature_c >= self.derate_threshold_c:
            self._below_threshold_since = None
            if self._shutdown_latched:
                self.state = ThermalState.SHUTDOWN
                return self._shutdown_result(data, "Chờ nhiệt độ xuống dưới 75°C liên tục 300 giây")
            if temperature_c > self.derate_threshold_c:
                self.state = ThermalState.DERATING
                final = requested_brightness_pct * self.derate_factor
                return ModuleResult("ThermalDeratingEngine", ModuleStatus.WARNING,
                                    self.state.value, data,
                                    {"final_brightness_pct": final, "shutdown_required": False,
                                     "derating_factor": self.derate_factor},
                                    {"calculation": "original_request * 0.8"}, None)
            self.state = ThermalState.NORMAL  # đúng 75°C: chưa vượt ngưỡng derate
            return ModuleResult("ThermalDeratingEngine", ModuleStatus.SUCCESS,
                                self.state.value, data,
                                {"final_brightness_pct": requested_brightness_pct,
                                 "shutdown_required": False, "derating_factor": 1.0},
                                {"recovery_timer": "RESET_AT_OR_ABOVE_75C"}, None)

        # Chỉ bắt đầu/duy trì bộ đếm khi nhiệt độ < 75°C.
        if self._below_threshold_since is None:
            self._below_threshold_since = now_seconds
        elapsed = max(0.0, now_seconds - self._below_threshold_since)
        if self._shutdown_latched:
            if elapsed >= self.recovery_seconds:
                self._shutdown_latched = False
                self.state = ThermalState.NORMAL
            else:
                self.state = ThermalState.SHUTDOWN
                return self._shutdown_result(data, "Đang chờ điều kiện hồi phục nhiệt", elapsed)
        else:
            self.state = ThermalState.NORMAL
        return ModuleResult("ThermalDeratingEngine", ModuleStatus.SUCCESS,
                            self.state.value, data,
                            {"final_brightness_pct": requested_brightness_pct,
                             "shutdown_required": False, "derating_factor": 1.0},
                            {"below_threshold_seconds": elapsed,
                             "recovery_seconds_required": self.recovery_seconds}, None)

    def _shutdown_result(self, data: dict, message: str, elapsed: float = 0.0) -> ModuleResult:
        return ModuleResult("ThermalDeratingEngine", ModuleStatus.ERROR,
                            ThermalState.SHUTDOWN.value, data,
                            {"final_brightness_pct": 0.0, "shutdown_required": True,
                             "derating_factor": 0.0},
                            {"below_threshold_seconds": elapsed,
                             "recovery_seconds_remaining": max(0.0, self.recovery_seconds - elapsed)},
                            ErrorInfo("THERMAL_RECOVERY_PENDING", message, "CRITICAL", True))

    @staticmethod
    def _error(code: str, message: str, data: dict) -> ModuleResult:
        return ModuleResult("ThermalDeratingEngine", ModuleStatus.ERROR, "ERROR",
                            data, {}, {}, ErrorInfo(code, message, "HIGH"))
