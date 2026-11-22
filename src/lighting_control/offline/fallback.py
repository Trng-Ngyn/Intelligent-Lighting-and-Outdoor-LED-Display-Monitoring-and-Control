"""Fallback lịch cục bộ; cảm biến ánh sáng chỉ hỗ trợ trong 05:00-05:30."""

from __future__ import annotations

from datetime import datetime, time as clock_time
from enum import Enum
from typing import Optional

from ..contracts import ErrorInfo, ModuleResult, ModuleStatus


class OfflineState(str, Enum):
    ONLINE = "ONLINE"
    WAITING_TIMEOUT = "WAITING_TIMEOUT"
    LOCAL_SCHEDULE = "LOCAL_SCHEDULE"
    CLOCK_FAULT = "CLOCK_FAULT"
    SENSOR_FAULT = "SENSOR_FAULT"


class OfflineFallbackManager:
    def __init__(self, mqtt_timeout_seconds: float = 300.0,
                 dark_lux: float = 50.0, bright_lux: float = 80.0,
                 stable_seconds: float = 120.0,
                 schedule: Optional[list[tuple[clock_time, clock_time, int]]] = None) -> None:
        if mqtt_timeout_seconds <= 0 or stable_seconds <= 0 or dark_lux >= bright_lux:
            raise ValueError("Cấu hình fallback không hợp lệ")
        self.mqtt_timeout_seconds = mqtt_timeout_seconds
        self.dark_lux = dark_lux
        self.bright_lux = bright_lux
        self.stable_seconds = stable_seconds
        self.schedule = schedule or [
            (clock_time(18, 0), clock_time(22, 0), 100),
            (clock_time(22, 0), clock_time(0, 0), 70),
            (clock_time(0, 0), clock_time(5, 0), 40),
        ]
        self._dark_since: Optional[float] = None
        self._bright_since: Optional[float] = None
        self._dawn_is_dark: Optional[bool] = None
        self._last_target_pct: Optional[int] = None

    def evaluate(self, *, mqtt_connected: bool, mqtt_disconnected_seconds: float,
                 local_time: Optional[datetime], clock_valid: bool,
                 lux: Optional[float], sensor_valid: bool,
                 now_seconds: float) -> ModuleResult:
        data = {"mqtt_connected": mqtt_connected,
                "mqtt_disconnected_seconds": mqtt_disconnected_seconds,
                "local_time": local_time.isoformat() if local_time else None,
                "clock_valid": clock_valid, "lux": lux,
                "sensor_valid": sensor_valid, "now_seconds": now_seconds}
        if mqtt_connected:
            self._reset_dawn_timers()
            return ModuleResult("OfflineFallbackManager", ModuleStatus.SUCCESS,
                                OfflineState.ONLINE.value, data,
                                {"fallback_active": False, "local_target_pct": None},
                                {"mqtt_timeout_seconds": self.mqtt_timeout_seconds}, None)
        if mqtt_disconnected_seconds <= self.mqtt_timeout_seconds:
            return ModuleResult("OfflineFallbackManager", ModuleStatus.SUCCESS,
                                OfflineState.WAITING_TIMEOUT.value, data,
                                {"fallback_active": False, "local_target_pct": None},
                                {"seconds_until_activation": self.mqtt_timeout_seconds - mqtt_disconnected_seconds}, None)
        if not clock_valid or local_time is None:
            return ModuleResult("OfflineFallbackManager", ModuleStatus.ERROR,
                                OfflineState.CLOCK_FAULT.value, data,
                                {"fallback_active": True, "local_target_pct": None,
                                 "action": "HOLD_LAST_APPROVED_AND_DEFER_TO_SAFETY_SUPERVISOR"},
                                {}, ErrorInfo("RTC_INVALID", "RTC/NTP không có thời gian hợp lệ; không thể chọn lịch", "CRITICAL", False))

        current = local_time.time().replace(tzinfo=None)
        target = self._schedule_target(current)
        diagnostics = {"schedule_window": None, "lux_hysteresis": None,
                       "mqtt_timeout_seconds": self.mqtt_timeout_seconds}
        error = None
        state = OfflineState.LOCAL_SCHEDULE
        status = ModuleStatus.SUCCESS
        if clock_time(5, 0) <= current < clock_time(5, 30):
            diagnostics["schedule_window"] = "05:00-05:30_AMBIENT_ASSIST"
            if not sensor_valid or lux is None:
                self._reset_dawn_timers()
                state, status = OfflineState.SENSOR_FAULT, ModuleStatus.WARNING
                target = self._last_target_pct if self._last_target_pct is not None else 40
                error = ErrorInfo("AMBIENT_SENSOR_FAULT",
                                  "Cảm biến lux lỗi; giữ mức đã biết hoặc mức lịch 40%, không coi lỗi là 0 lux",
                                  "HIGH", True)
            elif lux <= self.dark_lux:
                self._bright_since = None
                if self._dark_since is None:
                    self._dark_since = now_seconds
                if now_seconds - self._dark_since >= self.stable_seconds:
                    self._dawn_is_dark = True
                diagnostics["lux_hysteresis"] = "DARK_STABLE" if self._dawn_is_dark else "DARK_PENDING"
                target = 40 if self._dawn_is_dark else (self._last_target_pct if self._last_target_pct is not None else 40)
            elif lux >= self.bright_lux:
                self._dark_since = None
                if self._bright_since is None:
                    self._bright_since = now_seconds
                if now_seconds - self._bright_since >= self.stable_seconds:
                    self._dawn_is_dark = False
                diagnostics["lux_hysteresis"] = "BRIGHT_STABLE" if self._dawn_is_dark is False else "BRIGHT_PENDING"
                target = 0 if self._dawn_is_dark is False else (self._last_target_pct if self._last_target_pct is not None else 40)
            else:
                self._reset_dawn_timers()
                diagnostics["lux_hysteresis"] = "HOLD_PREVIOUS_IN_DEADBAND"
                target = self._last_target_pct if self._last_target_pct is not None else 40
        else:
            self._reset_dawn_timers()
            if target is None:
                diagnostics["schedule_window"] = "OUTSIDE_ACTIVE_WINDOWS"
            else:
                diagnostics["schedule_window"] = "FIXED_SCHEDULE"

        if target is not None:
            self._last_target_pct = target
        return ModuleResult("OfflineFallbackManager", status, state.value, data,
                            {"fallback_active": True, "local_target_pct": target,
                             "target_source": "LOCAL_SCHEDULE"}, diagnostics, error)

    def _schedule_target(self, current: clock_time) -> Optional[int]:
        for start, end, target in self.schedule:
            if start < end and start <= current < end:
                return target
            if start > end and (current >= start or current < end):
                return target
        return 0

    def _reset_dawn_timers(self) -> None:
        self._dark_since = None
        self._bright_since = None

