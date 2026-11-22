"""Thống nhất định dạng output của các module trong hệ thống điều khiển ánh sáng."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class ModuleStatus(str, Enum):
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass(frozen=True)
class ErrorInfo:
    code: str
    message: str
    severity: str = "MEDIUM"
    recoverable: bool = True
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModuleResult:
    module: str
    status: ModuleStatus
    state: str
    input: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    error: Optional[ErrorInfo] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        """Trả về dict chuẩn hóa của ModuleResult, có thể dùng để serialize sang JSON."""
        data = asdict(self)
        data["status"] = self.status.value
        if self.error is not None:
            data["error"] = asdict(self.error)
        return data
