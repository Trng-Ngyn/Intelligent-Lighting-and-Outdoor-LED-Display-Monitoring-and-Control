"""Canonical envelope và khóa HMAC cho lớp northbound Phương án C.

Lớp northbound dùng topic cấp gateway:
    pccom/v1/{tenant_id}/{site_id}/{gateway_id}/{category}

Danh tính thiết bị nằm trong envelope. Bridge chịu trách nhiệm:
- dịch payload southbound sang envelope chuẩn;
- ký northbound bằng khóa gateway;
- xác thực lệnh northbound rồi ký lại southbound bằng khóa thiết bị.

Module này không phụ thuộc paho/MQTT để có thể test thuần Python.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Mapping, Optional

from .northbound_topics import validate_category
from .signing import new_correlation_id, now_ms
from .topics import validate_device_type, validate_segment

SCHEMA_VERSION = "1.0.0"
DEFAULT_QUALITY = "GOOD"

# Tech Lead dùng trạng thái ack chữ thường; thiết bị IoT dùng chữ hoa.
ACK_STATUS_MAP = {
    "EXECUTED": "executed",
    "REJECTED": "rejected",
    "EXPIRED": "expired",
    "FAILED": "failed",
    "UNKNOWN": "unknown",
}


class NorthboundPayloadError(ValueError):
    """Envelope thiếu trường, sai kiểu hoặc sai định danh."""


def derive_gateway_key(
    master_secret: str,
    tenant_id: str,
    site_id: str,
    gateway_id: str,
) -> bytes:
    """Dẫn xuất khóa HMAC riêng cho gateway northbound.

    Khóa này tách khỏi khóa thiết bị southbound. Bridge dùng nó để ký
    telemetry/status/ack/alerts; Cloud/Core API dùng cùng công thức để xác
    thực và gửi lệnh.
    """
    if not master_secret:
        raise NorthboundPayloadError(
            "master_secret rỗng, không thể dẫn xuất khóa gateway"
        )
    identity = (
        f"{tenant_id}/{site_id}/gateway/{gateway_id}".encode("utf-8")
    )
    return hmac.new(
        master_secret.encode("utf-8"),
        identity,
        hashlib.sha256,
    ).digest()


def normalize_ack_status(status: Any) -> str:
    """Chuẩn hóa trạng thái result/ack về từ vựng Tech Lead."""
    raw = str(status or "unknown").strip()
    if not raw:
        return "unknown"
    return ACK_STATUS_MAP.get(raw.upper(), raw.lower())


def build_envelope(
    *,
    tenant_id: str,
    site_id: str,
    gateway_id: str,
    source_site_id: str,
    device_type: str,
    device_id: str,
    category: str,
    data: Any,
    source_time: Optional[int] = None,
    quality: str = DEFAULT_QUALITY,
    extra: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """Tạo envelope canonical dùng chung cho mọi category northbound."""
    tenant = validate_segment(tenant_id, "tenant_id")
    site = validate_segment(site_id, "site_id")
    gateway = validate_segment(gateway_id, "gateway_id")
    source_site = validate_segment(source_site_id, "source_site_id")
    dtype = validate_device_type(device_type)
    did = validate_segment(device_id, "device_id")
    cat = validate_category(category)

    if not isinstance(data, (dict, list, str, int, float, bool, type(None))):
        raise NorthboundPayloadError(
            f"data phải là JSON value, nhận được {type(data).__name__}"
        )

    now_sec = int(time.time())
    asset_id = did
    if isinstance(data, dict):
        asset_id = str(data.get("asset_id") or data.get("device_id") or did)
    if source_time is None and isinstance(data, dict):
        source_time = data.get("source_time") or data.get("device_time")
    if source_time is None:
        source_time = now_sec

    envelope = {
        "schema_version": SCHEMA_VERSION,
        "message_id": new_correlation_id(),
        "tenant_id": tenant,
        "site_id": site,
        "source_site_id": source_site,
        "gateway_id": gateway,
        "device_type": dtype,
        "device_id": did,
        "asset_id": asset_id,
        "category": cat,
        "source_time": int(source_time),
        "received_time": now_sec,
        "quality": quality,
        "data": data,
    }
    if extra:
        envelope.update(dict(extra))
    return envelope


def encode_envelope(envelope: Mapping[str, Any]) -> str:
    """Serialize envelope theo JSON compact, UTF-8 friendly."""
    return json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))


def parse_envelope(payload: bytes | str) -> dict[str, Any]:
    """Decode và kiểm tra tối thiểu một envelope northbound.

    Ngoại lệ:
        NorthboundPayloadError: Payload không phải JSON object hoặc thiếu
            trường định danh bắt buộc.
    """
    if isinstance(payload, bytes):
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise NorthboundPayloadError("Envelope không phải UTF-8") from exc
    elif isinstance(payload, str):
        text = payload
    else:
        raise NorthboundPayloadError("Envelope phải là bytes hoặc str")

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise NorthboundPayloadError(f"Envelope không phải JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise NorthboundPayloadError("Envelope phải là JSON object")

    required = (
        "tenant_id",
        "site_id",
        "gateway_id",
        "device_type",
        "device_id",
        "category",
        "data",
    )
    missing = [name for name in required if name not in data]
    if missing:
        raise NorthboundPayloadError(
            f"Envelope thiếu trường bắt buộc: {', '.join(missing)}"
        )

    validate_segment(str(data["tenant_id"]), "tenant_id")
    validate_segment(str(data["site_id"]), "site_id")
    validate_segment(str(data["gateway_id"]), "gateway_id")
    validate_device_type(str(data["device_type"]))
    validate_segment(str(data["device_id"]), "device_id")
    validate_category(str(data["category"]))
    return data


def envelope_device_key(
    envelope: Mapping[str, Any],
) -> tuple[str, str, str]:
    """Trả về khóa thiết bị (source_site_id, device_type, device_id)."""
    source_site = envelope.get("source_site_id")
    if not source_site:
        raise NorthboundPayloadError("Envelope thiếu source_site_id")
    return (
        str(source_site),
        str(envelope["device_type"]),
        str(envelope["device_id"]),
    )


def command_target(envelope: Mapping[str, Any]) -> tuple[str, str, str]:
    """Lấy target thiết bị từ lệnh northbound.

    Hỗ trợ cả dạng phẳng (asset_id/device_id) và dạng contracts
    (target: {asset_id/device_id}). Nếu thiếu device_type, caller phải tra
    registry theo device_id.
    """
    target = envelope.get("target")
    if isinstance(target, dict):
        device_id = target.get("device_id") or target.get("asset_id")
        device_type = target.get("device_type")
    else:
        device_id = envelope.get("device_id") or envelope.get("asset_id")
        device_type = envelope.get("device_type")

    if not device_id:
        raise NorthboundPayloadError("Lệnh northbound thiếu target device_id")
    source_site = envelope.get("source_site_id")
    if not source_site:
        raise NorthboundPayloadError("Lệnh northbound thiếu source_site_id")
    if not device_type:
        raise NorthboundPayloadError("Lệnh northbound thiếu device_type")
    return (
        str(source_site),
        str(device_type),
        str(device_id),
    )


def envelope_timestamp_ms() -> int:
    """Timestamp hiện tại dạng mili-giây cho log/ack extra."""
    return now_ms()
