"""Bộ ra quyết định ưu tiên an toàn, độc lập với adapter phần cứng."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SafetyAction(str, Enum):
    ALLOW = "ALLOW"
    LIMIT = "LIMIT"
    HOLD = "HOLD"
    REJECT = "REJECT"
    SHUTDOWN = "SHUTDOWN"


class SystemState(str, Enum):
    INITIALIZING = "INITIALIZING"
    NORMAL = "NORMAL"
    DERATING = "DERATING"
    OFFLINE_FALLBACK = "OFFLINE_FALLBACK"
    DEGRADED = "DEGRADED"
    THERMAL_SHUTDOWN = "THERMAL_SHUTDOWN"
    FAULT_SHUTDOWN = "FAULT_SHUTDOWN"
    RECOVERY_PENDING = "RECOVERY_PENDING"


@dataclass
class SafetyInput:
    requested_brightness_pct: Optional[float] = None
    schedule_brightness_pct: Optional[float] = None
    last_valid_brightness_pct: Optional[float] = None
    temperature_c: Optional[float] = None
    temperature_sensor_valid: bool = True
    thermal_shutdown: bool = False
    thermal_recovery_pending: bool = False
    thermal_derating: bool = False
    temperature_sensor_fault_brightness_pct: float = 30.0
    hardware_faults: list[str] = field(default_factory=list)
    ambient_sensor_valid: bool = True
    rtc_valid: bool = True
    mqtt_connected: bool = True
    mqtt_disconnected_seconds: float = 0.0
    local_schedule_valid: bool = True
    command_valid: bool = True
    replay_detected: bool = False
    dali_bus_ok: bool = True
    dali_controller_ok: bool = True
    fade_controller_ok: bool = True
    boot_state_valid: bool = True
    timestamp: Optional[str] = None


@dataclass
class SafetyDecision:
    decision_id: str
    timestamp: str
    system_state: str
    requested_brightness_pct: Optional[float]
    final_brightness_pct: float
    action: str
    execution_authorized: bool
    active_faults: list[dict]
    reason_codes: list[str]
    diagnostics: dict

    def to_dict(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "timestamp": self.timestamp,
            "system_state": self.system_state,
            "requested_brightness_pct": self.requested_brightness_pct,
            "final_brightness_pct": self.final_brightness_pct,
            "action": self.action,
            "execution_authorized": self.execution_authorized,
            "active_faults": self.active_faults,
            "reason_codes": self.reason_codes,
            "diagnostics": self.diagnostics,
        }


class SafetyDecisionEngine:
    """Chính sách: phần cứng nghiêm trọng > thermal shutdown > các giới hạn khác."""

    def decide(self, data: SafetyInput, *, faults: list[dict], decision_id: str,
               timestamp: str) -> SafetyDecision:
        requested = data.requested_brightness_pct
        reasons: list[str] = []
        diagnostics = {"physical_output": "UNKNOWN" if not data.dali_bus_ok else "NOT_VERIFIED",
                       "temperature_c": data.temperature_c,
                       "temperature_sensor_valid": data.temperature_sensor_valid}

        # Lỗi phần cứng nghiêm trọng luôn thắng mọi fallback, kể cả sensor fault.
        if data.hardware_faults:
            reasons.extend(data.hardware_faults)
            return self._decision(decision_id, timestamp, SystemState.FAULT_SHUTDOWN,
                                  requested, 0.0, SafetyAction.SHUTDOWN, True,
                                  faults, reasons, diagnostics)

        # Thermal shutdown thực tế/latch cũng luôn yêu cầu OFF.
        if data.thermal_shutdown or data.thermal_recovery_pending or (data.temperature_sensor_valid and
                                     data.temperature_c is not None and data.temperature_c > 90.0):
            reasons.append("THERMAL_RECOVERY_PENDING" if data.thermal_recovery_pending else "THERMAL_SHUTDOWN")
            state = SystemState.RECOVERY_PENDING if data.thermal_recovery_pending else SystemState.THERMAL_SHUTDOWN
            return self._decision(decision_id, timestamp, state,
                                  requested, 0.0, SafetyAction.SHUTDOWN, True,
                                  faults, reasons, diagnostics)

        if requested is not None and not 0 <= requested <= 100:
            return self._decision(decision_id, timestamp, SystemState.DEGRADED,
                                  requested, self._last_or_off(data), SafetyAction.REJECT,
                                  False, faults, ["BRIGHTNESS_OUT_OF_RANGE"], diagnostics)

        # Không phát lại lệnh không hợp lệ hoặc lệnh replay.
        if not data.command_valid or data.replay_detected:
            code = "COMMAND_REPLAY_REJECTED" if data.replay_detected else "INVALID_COMMAND_REJECTED"
            return self._decision(decision_id, timestamp, SystemState.DEGRADED,
                                  requested, self._last_or_off(data), SafetyAction.REJECT,
                                  False, faults, [code], diagnostics)

        if not data.boot_state_valid and data.last_valid_brightness_pct is None:
            return self._decision(decision_id, timestamp, SystemState.INITIALIZING,
                                  requested, 0.0, SafetyAction.SHUTDOWN, True,
                                  faults, ["NO_VALID_STORED_OUTPUT_STATE"], diagnostics)

        # DALI bus lỗi: không gửi lệnh mới; giữ logical target, physical output UNKNOWN.
        if not data.dali_bus_ok:
            return self._decision(decision_id, timestamp, SystemState.DEGRADED,
                                  requested, self._last_or_off(data), SafetyAction.HOLD,
                                  False, faults, ["DALI_BUS_FAULT", "PHYSICAL_OUTPUT_UNKNOWN"], diagnostics)
        if not data.dali_controller_ok:
            return self._decision(decision_id, timestamp, SystemState.DEGRADED,
                                  requested, self._last_or_off(data), SafetyAction.HOLD,
                                  False, faults, ["DALI_CONTROLLER_ERROR"], diagnostics)

        if not data.rtc_valid:
            held = self._last_or_off(data)
            reasons = ["RTC_INVALID"]
            if not data.temperature_sensor_valid or data.temperature_c is None:
                held = min(held, data.temperature_sensor_fault_brightness_pct)
                reasons.append("TEMPERATURE_SENSOR_FAULT_FIXED_30_CAP")
            elif data.thermal_derating or 75.0 < data.temperature_c <= 90.0:
                held *= 0.8
                reasons.append("THERMAL_DERATING_0_8")
            return self._decision(decision_id, timestamp, SystemState.DEGRADED,
                                  requested, held, SafetyAction.HOLD,
                                  False, faults, reasons, diagnostics)

        if not data.fade_controller_ok:
            return self._decision(decision_id, timestamp, SystemState.DEGRADED,
                                  requested, self._last_or_off(data), SafetyAction.HOLD,
                                  False, faults, ["FADE_CONTROLLER_FAULT"], diagnostics)

        # Khi offline >300s, chỉ dùng lịch cục bộ hợp lệ; không có lịch thì HOLD.
        offline = (not data.mqtt_connected and data.mqtt_disconnected_seconds > 300.0)
        if offline and not data.local_schedule_valid:
            return self._decision(decision_id, timestamp, SystemState.DEGRADED,
                                  requested, self._last_or_off(data), SafetyAction.HOLD,
                                  False, faults, ["OFFLINE_WITHOUT_VALID_SCHEDULE"], diagnostics)

        # Base request: operator/cloud request bị giới hạn bởi lịch khi có lịch.
        base = requested if requested is not None else data.last_valid_brightness_pct
        if offline:
            base = data.schedule_brightness_pct
            reasons.append("MQTT_OFFLINE_LOCAL_SCHEDULE")
        elif data.schedule_brightness_pct is not None:
            if base is None:
                base = data.schedule_brightness_pct
            elif data.schedule_brightness_pct < base:
                base = data.schedule_brightness_pct
                reasons.append("SCHEDULE_BRIGHTNESS_CAP")

        if base is None:
            base = 0.0
            reasons.append("NO_VALID_BRIGHTNESS_REQUEST")

        # Lỗi cảm biến lux: giữ mức trước đó, nhưng vẫn không được vượt giới hạn nhiệt.
        if not data.ambient_sensor_valid:
            reasons.append("AMBIENT_SENSOR_FAULT_HOLD")
            if data.last_valid_brightness_pct is not None:
                base = min(base, data.last_valid_brightness_pct)
            else:
                base = 0.0  # không có target hợp lệ để giữ; không tự bật đèn

        # Lỗi cảm biến nhiệt độ: 30% là mức mặc định/tối đa, không phải lệnh luôn bật.
        # Lịch/command OFF vẫn được phép kéo brightness xuống 0%.
        if not data.temperature_sensor_valid or data.temperature_c is None:
            base = min(base, data.temperature_sensor_fault_brightness_pct)
            reasons.append("TEMPERATURE_SENSOR_FAULT_FIXED_30_CAP")
            state = SystemState.DEGRADED
        else:
            state = SystemState.NORMAL

        if data.thermal_derating or (data.temperature_sensor_valid and
                                     data.temperature_c is not None and 75.0 < data.temperature_c <= 90.0):
            base *= 0.8
            reasons.append("THERMAL_DERATING_0_8")
            state = SystemState.DERATING

        if offline:
            state = SystemState.OFFLINE_FALLBACK
        if not data.ambient_sensor_valid or not data.temperature_sensor_valid:
            if state != SystemState.DERATING and not offline:
                state = SystemState.DEGRADED

        final = round(max(0.0, min(100.0, base)), 2)
        action = SafetyAction.ALLOW if not reasons else SafetyAction.LIMIT
        if data.last_valid_brightness_pct is not None and final == self._last_or_off(data) and (not data.temperature_sensor_valid or not data.ambient_sensor_valid):
            action = SafetyAction.HOLD
        return self._decision(decision_id, timestamp, state, requested, final,
                              action, True, faults, reasons or ["NO_ACTIVE_FAULT"], diagnostics)

    @staticmethod
    def _last_or_off(data: SafetyInput) -> float:
        if data.last_valid_brightness_pct is None:
            return 0.0
        return max(0.0, min(100.0, data.last_valid_brightness_pct))

    @staticmethod
    def _decision(decision_id, timestamp, state, requested, final, action,
                  authorized, faults, reasons, diagnostics) -> SafetyDecision:
        diagnostics = dict(diagnostics)
        diagnostics["execution_status"] = "AUTHORIZED" if authorized else "NOT_AUTHORIZED"
        return SafetyDecision(decision_id, timestamp, state.value, requested,
                              round(final, 2), action.value, authorized,
                              faults, reasons, diagnostics)
