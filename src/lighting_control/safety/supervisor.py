"""Điểm vào trung tâm: thu thập trạng thái module và phát SafetyDecision."""
from __future__ import annotations

from datetime import datetime, timezone
from itertools import count
from typing import Optional

from ..contracts import ModuleResult
from .decision_engine import SafetyDecision, SafetyDecisionEngine, SafetyInput
from .fault_manager import FaultManager


class SafetySupervisor:
    def __init__(self, temperature_sensor_fault_brightness_pct: float = 30.0,
                 mqtt_offline_timeout_seconds: float = 300.0) -> None:
        if not 0 <= temperature_sensor_fault_brightness_pct <= 100:
            raise ValueError("Mức sáng fallback nhiệt độ phải thuộc [0,100]")
        if mqtt_offline_timeout_seconds <= 0:
            raise ValueError("MQTT timeout phải lớn hơn 0")
        self.temperature_sensor_fault_brightness_pct = temperature_sensor_fault_brightness_pct
        self.mqtt_offline_timeout_seconds = mqtt_offline_timeout_seconds
        self.fault_manager = FaultManager()
        self.decision_engine = SafetyDecisionEngine()
        self._ids = count(1)

    def evaluate(self, *, requested_brightness_pct: Optional[float] = None,
                 schedule_brightness_pct: Optional[float] = None,
                 last_valid_brightness_pct: Optional[float] = None,
                 temperature_c: Optional[float] = None,
                 temperature_sensor_valid: bool = True,
                 thermal_shutdown: bool = False, thermal_recovery_pending: bool = False,
                 thermal_derating: bool = False,
                 hardware_faults: Optional[list[str]] = None,
                 ambient_sensor_valid: bool = True, rtc_valid: bool = True,
                 mqtt_connected: bool = True, mqtt_disconnected_seconds: float = 0.0,
                 local_schedule_valid: bool = True, command_valid: bool = True,
                 replay_detected: bool = False, dali_bus_ok: bool = True,
                 dali_controller_ok: bool = True,
                 fade_controller_ok: bool = True, boot_state_valid: bool = True,
                 module_results: Optional[list[ModuleResult]] = None,
                 timestamp: Optional[str] = None) -> SafetyDecision:
        """Tạo quyết định mới; không trực tiếp gửi lệnh DALI.

        `schedule_brightness_pct=0` là OFF có chủ đích; None nghĩa là không có
        giới hạn/lịch được cung cấp trong chu kỳ này.
        """
        # Kết quả module có thể được truyền trực tiếp; chuẩn hóa lỗi về input policy.
        for result in module_results or []:
            code = result.error.code if result.error else ""
            if result.module == "ThermalDeratingEngine":
                if code == "TEMPERATURE_SENSOR_FAULT" or result.state == "SENSOR_FAULT":
                    temperature_sensor_valid = False
                if code == "THERMAL_SHUTDOWN":
                    thermal_shutdown = True
                if code == "THERMAL_RECOVERY_PENDING":
                    thermal_recovery_pending = True
                if result.state == "DERATING":
                    thermal_derating = True
            elif result.module == "OfflineFallbackManager":
                if result.state == "CLOCK_FAULT":
                    rtc_valid = False
                if result.state == "SENSOR_FAULT":
                    ambient_sensor_valid = False
                if result.output.get("fallback_active"):
                    mqtt_connected = False
                    mqtt_disconnected_seconds = max(mqtt_disconnected_seconds,
                                                    self.mqtt_offline_timeout_seconds + 1)
                    if schedule_brightness_pct is None and result.output.get("local_target_pct") is not None:
                        schedule_brightness_pct = float(result.output["local_target_pct"])
            elif result.module == "DaliDimmingController" and result.status.value == "ERROR":
                dali_controller_ok = False
                if code in ("DALI_BUS_EXCEPTION", "DALI_BUS_SEND_FAILED"):
                    dali_bus_ok = False
            elif result.module == "FadeController" and result.status.value == "ERROR":
                fade_controller_ok = False

        now = timestamp or datetime.now(timezone.utc).isoformat()
        faults = self._collect_faults(
            temperature_sensor_valid, temperature_c, thermal_shutdown or thermal_recovery_pending,
            hardware_faults or [], ambient_sensor_valid, rtc_valid,
            mqtt_connected, mqtt_disconnected_seconds, command_valid,
            replay_detected, dali_bus_ok, fade_controller_ok, module_results, now,
        )
        data = SafetyInput(
            requested_brightness_pct=requested_brightness_pct,
            schedule_brightness_pct=schedule_brightness_pct,
            last_valid_brightness_pct=last_valid_brightness_pct,
            temperature_c=temperature_c,
            temperature_sensor_valid=temperature_sensor_valid,
            thermal_shutdown=thermal_shutdown,
            thermal_recovery_pending=thermal_recovery_pending,
            thermal_derating=thermal_derating,
            temperature_sensor_fault_brightness_pct=self.temperature_sensor_fault_brightness_pct,
            hardware_faults=hardware_faults or [],
            ambient_sensor_valid=ambient_sensor_valid,
            rtc_valid=rtc_valid,
            mqtt_connected=mqtt_connected,
            mqtt_disconnected_seconds=mqtt_disconnected_seconds,
            local_schedule_valid=local_schedule_valid,
            command_valid=command_valid,
            replay_detected=replay_detected,
            dali_bus_ok=dali_bus_ok,
            dali_controller_ok=dali_controller_ok,
            fade_controller_ok=fade_controller_ok,
            boot_state_valid=boot_state_valid,
            timestamp=now,
        )
        decision = self.decision_engine.decide(
            data, faults=faults, decision_id=f"safety-{next(self._ids):06d}", timestamp=now
        )
        return decision

    def _collect_faults(self, temp_valid, temp, thermal_shutdown, hardware_faults,
                        ambient_valid, rtc_valid, mqtt_connected, mqtt_seconds,
                        command_valid, replay, dali_ok, fade_ok, module_results, now):
        self.fault_manager = FaultManager()  # snapshot per decision, no stale faults
        if hardware_faults:
            for code in hardware_faults:
                self.fault_manager.raise_fault(code, "CRITICAL", "Hardware", code,
                                               recoverable=False, timestamp=now)
        if thermal_shutdown or (temp_valid and temp is not None and temp > 90):
            self.fault_manager.raise_fault("THERMAL_SHUTDOWN", "CRITICAL", "ThermalEngine",
                                           "Nhiệt độ vượt ngưỡng shutdown", False, now)
        if not temp_valid or temp is None:
            self.fault_manager.raise_fault("TEMPERATURE_SENSOR_FAULT", "CRITICAL", "ThermalEngine",
                                           "Cảm biến nhiệt độ không hợp lệ", True, now)
        if not ambient_valid:
            self.fault_manager.raise_fault("AMBIENT_SENSOR_FAULT", "HIGH", "OfflineFallbackManager",
                                           "Cảm biến ánh sáng không hợp lệ", True, now)
        if not rtc_valid:
            self.fault_manager.raise_fault("RTC_INVALID", "CRITICAL", "Clock",
                                           "Thời gian hệ thống không đáng tin cậy", True, now)
        if not mqtt_connected and mqtt_seconds > self.mqtt_offline_timeout_seconds:
            self.fault_manager.raise_fault("MQTT_OFFLINE", "WARNING", "MQTT",
                                           "Mất kết nối MQTT quá thời gian cho phép", True, now)
        if not command_valid:
            self.fault_manager.raise_fault("INVALID_COMMAND", "HIGH", "CommandValidator",
                                           "Lệnh điều khiển không hợp lệ", False, now)
        if replay:
            self.fault_manager.raise_fault("COMMAND_REPLAY", "HIGH", "CommandValidator",
                                           "Phát hiện lệnh replay", False, now)
        if not dali_ok:
            self.fault_manager.raise_fault("DALI_BUS_FAULT", "CRITICAL", "DaliController",
                                           "Không thể truyền lệnh trên bus DALI", True, now)
        if not fade_ok:
            self.fault_manager.raise_fault("FADE_CONTROLLER_FAULT", "ERROR", "FadeController",
                                           "Fade Controller không sẵn sàng", True, now)
        for result in module_results or []:
            if result.status.value == "ERROR" and result.error:
                self.fault_manager.raise_fault(result.error.code, result.error.severity,
                                               result.module, result.error.message,
                                               result.error.recoverable, result.timestamp)
        return self.fault_manager.to_list()
