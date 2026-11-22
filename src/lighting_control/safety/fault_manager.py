"""Quản lý tập lỗi đang hoạt động của Safety Supervisor."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Iterable


@dataclass(frozen=True)
class FaultInfo:
    fault_code: str
    fault_level: str
    source_module: str
    timestamp: str
    description: str
    recoverable: bool
    active: bool = True


class FaultManager:
    """Lưu lỗi theo mã; cập nhật lại lỗi cùng mã thay vì tạo bản ghi trùng."""

    def __init__(self) -> None:
        self._faults: dict[str, FaultInfo] = {}

    def raise_fault(self, fault_code: str, fault_level: str, source_module: str,
                    description: str, recoverable: bool = True,
                    timestamp: str | None = None) -> FaultInfo:
        if not fault_code:
            raise ValueError("fault_code không được để trống")
        fault = FaultInfo(
            fault_code=fault_code,
            fault_level=fault_level.upper(),
            source_module=source_module,
            timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
            description=description,
            recoverable=recoverable,
            active=True,
        )
        self._faults[fault_code] = fault
        return fault

    def clear_fault(self, fault_code: str) -> None:
        self._faults.pop(fault_code, None)

    def replace_active(self, faults: Iterable[FaultInfo]) -> None:
        self._faults = {fault.fault_code: fault for fault in faults if fault.active}

    def active_faults(self) -> list[FaultInfo]:
        return list(self._faults.values())

    def to_list(self) -> list[dict]:
        return [asdict(fault) for fault in self.active_faults()]
