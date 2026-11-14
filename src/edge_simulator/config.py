"""Đọc và kiểm tra cấu hình cho Virtual Edge Simulator.

Vị trí trong luồng: file này là điểm vào cấu hình của phía Simulator. Mọi
thông số như broker, danh sách site/device, chu kỳ telemetry, Keep Alive,
cửa sổ chống replay và khóa ký đều lấy từ đây, không hard-code trong code.

Thứ tự ưu tiên:
1. Đường dẫn truyền vào hàm load_config().
2. Biến môi trường SIM_CONFIG.
3. config.json ở thư mục hiện tại.
4. config.example.json ở thư mục hiện tại hoặc gốc repo.

Các biến môi trường SIM_* sẽ override giá trị trong file, phù hợp khi chạy
CI hoặc không muốn ghi khóa thật xuống đĩa.

Xem src/edge_simulator/README.md và config.example.json.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

from iot_protocol.signing import DEFAULT_REPLAY_WINDOW_MS
from iot_protocol.topics import (
    validate_device_type,
    validate_segment,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_NAME = "config.json"
EXAMPLE_CONFIG_NAME = "config.example.json"
ALLOWED_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


class ConfigError(ValueError):
    """Cấu hình thiếu trường, sai kiểu hoặc vi phạm ràng buộc an toàn."""


@dataclass(frozen=True)
class BrokerConfig:
    """Thông tin kết nối broker MQTT 5."""

    host: str
    port: int = 1883
    username: Optional[str] = None
    password: Optional[str] = None
    use_tls: bool = False
    client_id_prefix: str = "pcvsim"


@dataclass(frozen=True)
class DeviceSpec:
    """Một thiết bị ngoại vi giả lập."""

    site_id: str
    device_type: str
    device_id: str
    initial_brightness: int = 50

    @property
    def key(self) -> tuple[str, str, str]:
        """Khóa định danh dùng cho index/ACL."""
        return (self.site_id, self.device_type, self.device_id)


@dataclass(frozen=True)
class SimulatorSettings:
    """Thông số vận hành của simulator."""

    telemetry_interval_sec: float = 15.0
    keep_alive_sec: int = 15
    replay_window_ms: int = DEFAULT_REPLAY_WINDOW_MS
    log_level: str = "INFO"
    crash_after_sec: Optional[float] = None
    max_devices: Optional[int] = None


@dataclass(frozen=True)
class SecurityConfig:
    """Cấu hình bảo mật (khóa gốc để dẫn xuất khóa từng thiết bị)."""

    signing_secret: str


@dataclass(frozen=True)
class SimulatorConfig:
    """Toàn bộ cấu hình đã kiểm tra và mở rộng danh sách thiết bị."""

    broker: BrokerConfig
    settings: SimulatorSettings
    security: SecurityConfig
    devices: tuple[DeviceSpec, ...]
    source_path: Path

    def device_index(self) -> dict[tuple[str, str, str], DeviceSpec]:
        """Trả về index tra cứu thiết bị theo (site, type, id)."""
        return {device.key: device for device in self.devices}


def _read_json(path: Path) -> dict[str, Any]:
    """Đọc file JSON UTF-8 và trả về dict gốc."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"Không tìm thấy file cấu hình: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"JSON không hợp lệ trong {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError(f"File cấu hình phải là JSON object: {path}")
    return data


def _env_str(name: str) -> Optional[str]:
    """Đọc biến môi trường; chuỗi rỗng được coi như không đặt."""
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return None
    return value.strip()


def _env_int(name: str) -> Optional[int]:
    """Đọc biến môi trường dạng int, báo lỗi rõ nếu sai."""
    raw = _env_str(name)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} phải là số nguyên, nhận được {raw!r}") from exc


def _env_float(name: str) -> Optional[float]:
    """Đọc biến môi trường dạng float, báo lỗi rõ nếu sai."""
    raw = _env_str(name)
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} phải là số thực, nhận được {raw!r}") from exc


def _env_bool(name: str) -> Optional[bool]:
    """Đọc biến môi trường dạng bool (1/true/yes/on)."""
    raw = _env_str(name)
    if raw is None:
        return None
    return raw.lower() in {"1", "true", "yes", "on"}


def _require_mapping(value: Any, name: str) -> dict[str, Any]:
    """Bắt buộc một trường phải là JSON object."""
    if not isinstance(value, dict):
        raise ConfigError(f"{name} phải là object")
    return value


def _require_str(value: Any, name: str) -> str:
    """Bắt buộc một trường phải là chuỗi không rỗng."""
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{name} phải là chuỗi không rỗng")
    return value.strip()


def _require_int(value: Any, name: str, minimum: int = 0) -> int:
    """Bắt buộc một trường phải là int >= minimum."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{name} phải là số nguyên")
    if value < minimum:
        raise ConfigError(f"{name} phải >= {minimum}")
    return value


def _resolve_config_path(explicit_path: Optional[str]) -> Path:
    """Xác định file cấu hình theo thứ tự ưu tiên đã mô tả ở đầu file."""
    if explicit_path:
        path = Path(explicit_path).expanduser().resolve()
        if not path.is_file():
            raise ConfigError(f"Không tìm thấy file cấu hình: {path}")
        return path

    env_path = _env_str("SIM_CONFIG")
    if env_path:
        path = Path(env_path).expanduser().resolve()
        if not path.is_file():
            raise ConfigError(f"SIM_CONFIG trỏ tới file không tồn tại: {path}")
        return path

    candidates = [
        Path.cwd() / DEFAULT_CONFIG_NAME,
        Path.cwd() / EXAMPLE_CONFIG_NAME,
        REPO_ROOT / DEFAULT_CONFIG_NAME,
        REPO_ROOT / EXAMPLE_CONFIG_NAME,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()

    raise ConfigError(
        "Không tìm thấy config.json/config.example.json. "
        "Hãy copy config.example.json thành config.json và đặt khóa ký."
    )


def _expand_device_groups(
    groups: Iterable[Any],
    max_devices: Optional[int],
) -> tuple[DeviceSpec, ...]:
    """Mở rộng các nhóm thiết bị (count/prefix hoặc device_ids) thành danh sách.

    Tham số:
        groups: Mảng JSON mô tả nhóm thiết bị.
        max_devices: Giới hạn số thiết bị sau khi mở rộng (dùng khi test).

    Trả về:
        Tuple DeviceSpec không trùng khóa.

    Ngoại lệ:
        ConfigError: Nhóm sai cấu trúc, device_id trùng hoặc vượt giới hạn.
    """
    devices: list[DeviceSpec] = []
    seen: set[tuple[str, str, str]] = set()

    for index, raw_group in enumerate(groups):
        group = _require_mapping(raw_group, f"devices[{index}]")
        site_id = validate_segment(
            _require_str(group.get("site_id"), f"devices[{index}].site_id"),
            "site_id",
        )
        device_type = validate_device_type(
            _require_str(
                group.get("device_type"),
                f"devices[{index}].device_type",
            )
        )
        initial = _require_int(
            group.get("initial_brightness", 50),
            f"devices[{index}].initial_brightness",
            minimum=0,
        )
        if initial > 100:
            raise ConfigError(
                f"devices[{index}].initial_brightness phải <= 100"
            )

        raw_ids = group.get("device_ids")
        if raw_ids is not None:
            if not isinstance(raw_ids, list) or not raw_ids:
                raise ConfigError(
                    f"devices[{index}].device_ids phải là mảng không rỗng"
                )
            device_ids = [
                validate_segment(
                    _require_str(item, f"devices[{index}].device_ids[]"),
                    "device_id",
                )
                for item in raw_ids
            ]
        else:
            prefix = _require_str(
                group.get("device_id_prefix"),
                f"devices[{index}].device_id_prefix",
            )
            count = _require_int(
                group.get("count"),
                f"devices[{index}].count",
                minimum=1,
            )
            start_index = _require_int(
                group.get("start_index", 1),
                f"devices[{index}].start_index",
                minimum=1,
            )
            width = _require_int(
                group.get("index_width", 3),
                f"devices[{index}].index_width",
                minimum=1,
            )
            if width > 12:
                raise ConfigError(
                    f"devices[{index}].index_width không được > 12"
                )
            if count > 10_000:
                raise ConfigError(
                    f"devices[{index}].count quá lớn (tối đa 10000)"
                )
            device_ids = [
                validate_segment(
                    f"{prefix}{number:0{width}d}",
                    "device_id",
                )
                for number in range(start_index, start_index + count)
            ]

        for device_id in device_ids:
            key = (site_id, device_type, device_id)
            if key in seen:
                raise ConfigError(
                    "Thiết bị bị trùng: "
                    f"{site_id}/{device_type}/{device_id}"
                )
            seen.add(key)
            devices.append(
                DeviceSpec(
                    site_id=site_id,
                    device_type=device_type,
                    device_id=device_id,
                    initial_brightness=initial,
                )
            )

    if max_devices is not None:
        devices = devices[:max_devices]

    if not devices:
        raise ConfigError("Cấu hình không có thiết bị nào")
    return tuple(devices)


def load_config(explicit_path: Optional[str] = None) -> SimulatorConfig:
    """Đọc file cấu hình và áp dụng override từ biến môi trường.

    Tham số:
        explicit_path: Đường dẫn file JSON (thường lấy từ --config).

    Trả về:
        SimulatorConfig đã kiểm tra.

    Ngoại lệ:
        ConfigError: File không tồn tại, JSON sai, thiếu trường hoặc giá trị
            nằm ngoài miền hợp lệ.
    """
    path = _resolve_config_path(explicit_path)
    data = _read_json(path)

    broker_raw = _require_mapping(data.get("broker", {}), "broker")
    settings_raw = _require_mapping(data.get("simulator", {}), "simulator")
    security_raw = _require_mapping(data.get("security", {}), "security")

    host = _env_str("SIM_BROKER_HOST") or _require_str(
        broker_raw.get("host"),
        "broker.host",
    )
    port = _env_int("SIM_BROKER_PORT") or _require_int(
        broker_raw.get("port", 1883),
        "broker.port",
        minimum=1,
    )
    if port > 65535:
        raise ConfigError("broker.port phải <= 65535")

    username = _env_str("SIM_BROKER_USERNAME")
    if username is None:
        username = broker_raw.get("username") or None
    password = _env_str("SIM_BROKER_PASSWORD")
    if password is None:
        password = broker_raw.get("password") or None
    use_tls = _env_bool("SIM_BROKER_TLS")
    if use_tls is None:
        use_tls = bool(broker_raw.get("use_tls", False))

    broker = BrokerConfig(
        host=host,
        port=port,
        username=username,
        password=password,
        use_tls=use_tls,
        client_id_prefix=_require_str(
            broker_raw.get("client_id_prefix", "pcvsim"),
            "broker.client_id_prefix",
        ),
    )

    telemetry_interval = _env_float("SIM_TELEMETRY_INTERVAL_SEC")
    if telemetry_interval is None:
        telemetry_interval = float(
            settings_raw.get("telemetry_interval_sec", 15.0)
        )
    if telemetry_interval <= 0:
        raise ConfigError("telemetry_interval_sec phải > 0")

    keep_alive = _env_int("SIM_KEEP_ALIVE_SEC")
    if keep_alive is None:
        keep_alive = _require_int(
            settings_raw.get("keep_alive_sec", 15),
            "simulator.keep_alive_sec",
            minimum=1,
        )

    replay_window = _env_int("SIM_REPLAY_WINDOW_MS")
    if replay_window is None:
        replay_window = _require_int(
            settings_raw.get("replay_window_ms", DEFAULT_REPLAY_WINDOW_MS),
            "simulator.replay_window_ms",
            minimum=1,
        )

    log_level = (
        _env_str("SIM_LOG_LEVEL")
        or _require_str(
            settings_raw.get("log_level", "INFO"),
            "simulator.log_level",
        )
    ).upper()
    if log_level not in ALLOWED_LOG_LEVELS:
        raise ConfigError(
            f"simulator.log_level phải thuộc {sorted(ALLOWED_LOG_LEVELS)}"
        )

    crash_after = _env_float("SIM_CRASH_AFTER_SEC")
    if crash_after is None and settings_raw.get("crash_after_sec") is not None:
        crash_after = float(settings_raw["crash_after_sec"])
    if crash_after is not None and crash_after <= 0:
        raise ConfigError("crash_after_sec phải > 0 hoặc null")

    max_devices = _env_int("SIM_MAX_DEVICES")
    if max_devices is None and settings_raw.get("max_devices") is not None:
        max_devices = _require_int(
            settings_raw["max_devices"],
            "simulator.max_devices",
            minimum=1,
        )
    if max_devices is not None and max_devices < 1:
        raise ConfigError("max_devices phải >= 1")

    signing_secret = (
        _env_str("SIM_SIGNING_SECRET")
        or _require_str(
            security_raw.get("signing_secret"),
            "security.signing_secret",
        )
    )
    if len(signing_secret) < 16:
        raise ConfigError(
            "security.signing_secret phải dài ít nhất 16 ký tự "
            "(khóa chỉ dùng cho dev/test, không commit khóa thật)"
        )

    raw_groups = data.get("devices")
    if not isinstance(raw_groups, list) or not raw_groups:
        raise ConfigError("devices phải là mảng không rỗng")

    devices = _expand_device_groups(raw_groups, max_devices)

    return SimulatorConfig(
        broker=broker,
        settings=SimulatorSettings(
            telemetry_interval_sec=telemetry_interval,
            keep_alive_sec=keep_alive,
            replay_window_ms=replay_window,
            log_level=log_level,
            crash_after_sec=crash_after,
            max_devices=max_devices,
        ),
        security=SecurityConfig(signing_secret=signing_secret),
        devices=devices,
        source_path=path,
    )
