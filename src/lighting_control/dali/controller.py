"""Điều khiển DALI ở mức logic; transport và đường cong arc-power được inject."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, Protocol

from ..contracts import ErrorInfo, ModuleResult, ModuleStatus


class DaliAddressType(str, Enum):
    SHORT = "SHORT"
    GROUP = "GROUP"
    BROADCAST = "BROADCAST"


@dataclass(frozen=True)
class DaliAddress:
    address_type: DaliAddressType
    value: Optional[int] = None

    def __post_init__(self) -> None:
        if self.address_type == DaliAddressType.SHORT and (
            self.value is None or not 0 <= self.value <= 63
        ):
            raise ValueError("DALI short address phải nằm trong [0, 63]")
        if self.address_type == DaliAddressType.GROUP and (
            self.value is None or not 0 <= self.value <= 15
        ):
            raise ValueError("DALI group address phải nằm trong [0, 15]")
        if self.address_type == DaliAddressType.BROADCAST and self.value is not None:
            raise ValueError("Broadcast không nhận value")


@dataclass
class DaliDevice:
    device_id: str
    address: DaliAddress
    min_level: int = 1
    max_level: int = 254
    online: Optional[bool] = None

    def __post_init__(self) -> None:
        if not self.device_id:
            raise ValueError("device_id không được rỗng")
        if not 1 <= self.min_level <= 254:
            raise ValueError("min_level phải nằm trong [1, 254]")
        if not self.min_level <= self.max_level <= 254:
            raise ValueError("max_level phải nằm trong [min_level, 254]")


class DaliBus(Protocol):
    """Adapter bus phải tự đảm bảo timing/Manchester và điện áp DALI phù hợp."""

    def send_arc_power(self, address: DaliAddress, arc_level: int) -> bool: ...
    def set_fade_time(self, address: DaliAddress, setting: int) -> bool: ...


class DaliDimmingController:
    """Quản lý thiết bị DALI, không coi gửi lệnh thành công là ánh sáng đã xác minh."""

    def __init__(
        self,
        bus: DaliBus,
        arc_power_mapper: Optional[Callable[[float, DaliDevice], int]] = None,
    ) -> None:
        self.bus = bus
        self.arc_power_mapper = arc_power_mapper
        self.devices: dict[str, DaliDevice] = {}

    def register_device(self, device: DaliDevice) -> None:
        if device.device_id in self.devices:
            raise ValueError(f"Thiết bị đã tồn tại: {device.device_id}")
        self.devices[device.device_id] = device

    def set_brightness(
        self,
        device_id: str,
        brightness_pct: float,
    ) -> ModuleResult:
        data = {"device_id": device_id, "brightness_pct": brightness_pct}
        device = self.devices.get(device_id)
        if device is None:
            return self._error("DEVICE_NOT_FOUND", "Không tìm thấy thiết bị DALI", data)
        if not 0 <= brightness_pct <= 100:
            return self._error("BRIGHTNESS_OUT_OF_RANGE", "Độ sáng phải thuộc [0, 100]%", data)
        if self.arc_power_mapper is None:
            return self._error(
                "CURVE_NOT_CONFIGURED",
                "Chưa cấu hình bộ chuyển đổi phần trăm sang DALI arc-power; chờ đặc tả đường cong Subtask 3",
                data,
            )
        try:
            if brightness_pct == 0:
                arc_level = 0
            else:
                arc_level = int(self.arc_power_mapper(brightness_pct, device))
                if not device.min_level <= arc_level <= device.max_level:
                    raise ValueError("Arc-power mapper trả về mức ngoài giới hạn thiết bị")
        except Exception as exc:  # mapper có thể là adapter bên ngoài
            return self._error("ARC_POWER_MAPPING_FAILED", str(exc), data)

        try:
            sent = bool(self.bus.send_arc_power(device.address, arc_level))
        except Exception as exc:
            return self._error("DALI_BUS_EXCEPTION", str(exc), data)
        if not sent:
            return self._error("DALI_BUS_SEND_FAILED", "Bus không xác nhận đã gửi frame", data)

        return ModuleResult(
            module="DaliDimmingController",
            status=ModuleStatus.WARNING,
            state="UNVERIFIED",
            input=data,
            output={"arc_power_level": arc_level, "command_sent": True,
                     "physical_output_verified": False},
            diagnostics={"address_type": device.address.address_type.value,
                         "address": device.address.value,
                         "verification": "NOT_AVAILABLE"},
            error=ErrorInfo(
                "OUTPUT_UNVERIFIED",
                "Lệnh đã gửi nhưng chưa có phản hồi đo lường để xác minh ánh sáng thực tế",
                severity="LOW",
                recoverable=True,
            ),
        )

    def set_fade_time(self, device_id: str, setting: int) -> ModuleResult:
        data = {"device_id": device_id, "fade_time_setting": setting}
        device = self.devices.get(device_id)
        if device is None:
            return self._error("DEVICE_NOT_FOUND", "Không tìm thấy thiết bị DALI", data)
        if not 1 <= setting <= 15:
            return self._error("FADE_SETTING_OUT_OF_RANGE", "Fade time setting phải thuộc [1, 15]", data)
        try:
            sent = bool(self.bus.set_fade_time(device.address, setting))
        except Exception as exc:
            return self._error("DALI_BUS_EXCEPTION", str(exc), data)
        if not sent:
            return self._error("DALI_BUS_SEND_FAILED", "Không gửi được cấu hình fade time", data)
        nominal = {1: .7, 2: 1.0, 3: 1.4, 4: 2.0, 5: 2.8, 6: 4.0, 7: 5.7,
                   8: 8.0, 9: 11.3, 10: 16.0, 11: 22.6, 12: 32.0,
                   13: 45.3, 14: 64.0, 15: 90.5}[setting]
        return ModuleResult(
            "DaliDimmingController", ModuleStatus.WARNING, "FADE_SETTING_SENT",
            data, {"nominal_fade_seconds": nominal, "command_sent": True,
                   "physical_fade_verified": False},
            {"verification": "NOT_AVAILABLE"},
            ErrorInfo("FADE_UNVERIFIED", "Chưa xác minh thời gian fade vật lý", "LOW"),
        )

    @staticmethod
    def _error(code: str, message: str, data: dict) -> ModuleResult:
        return ModuleResult("DaliDimmingController", ModuleStatus.ERROR, "ERROR",
                            data, {}, {}, ErrorInfo(code, message, "HIGH"))
