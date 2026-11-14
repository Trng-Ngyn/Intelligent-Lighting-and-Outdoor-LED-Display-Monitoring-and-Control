"""Xây dựng và xác thực bộ User Properties MQTT 5 bắt buộc.

Mọi bản tin trong hệ thống phải có:
- correlation_id: UUID4, dùng chung giữa lệnh và phản hồi.
- ts_ms: thời điểm tạo bản tin (epoch mili-giây).
- signature: HMAC-SHA256 trên chuỗi canonical.

Vị trí trong luồng: Simulator/Cloud tạo header trước khi publish; phía nhận
gọi verify_envelope() để từ chối bản tin thiếu/sai header hoặc bị replay.

Xem docs/specifications/MQTT5_COMMUNICATION_PROTOCOL.md để biết bảng header,
hành vi khi lỗi và mã alert tương ứng.
"""

from __future__ import annotations

from typing import Iterable, Mapping, Optional

from .signing import (
    ReplayGuard,
    SignatureError,
    new_correlation_id,
    now_ms,
    sign_message,
    verify_message,
)

USER_PROP_CORRELATION_ID = "correlation_id"
USER_PROP_TS_MS = "ts_ms"
USER_PROP_SIGNATURE = "signature"

REQUIRED_USER_PROPERTIES = (
    USER_PROP_CORRELATION_ID,
    USER_PROP_TS_MS,
    USER_PROP_SIGNATURE,
)

ALERT_HEADER_MISSING = "SEC_HEADER_MISSING"
ALERT_SIGNATURE_INVALID = "SEC_SIGNATURE_INVALID"
ALERT_REPLAY_DETECTED = "SEC_REPLAY_DETECTED"
ALERT_COMMAND_EXPIRED = "CMD_EXPIRED"
ALERT_INVALID_PAYLOAD = "PROTOCOL_INVALID_PAYLOAD"
ALERT_UNSUPPORTED_ACTION = "CMD_UNSUPPORTED_ACTION"


class HeaderError(ValueError):
    """Thiếu header bắt buộc, trùng khóa hoặc sai định dạng."""


def normalize_user_properties(
    raw_properties: Optional[
        Mapping[str, str] | Iterable[tuple[str, str]]
    ],
) -> dict[str, str]:
    """Chuyển User Properties từ paho/dict về dict chuẩn.

    Tham số:
        raw_properties: None, dict, hoặc list các cặp (key, value) của paho.

    Trả về:
        Dict key -> value. Chỉ các khóa bắt buộc xuất hiện một lần; nếu một
        khóa bắt buộc bị lặp, ném HeaderError để tránh kẻ tấn công lợi dụng
        thứ tự khóa không rõ ràng.

    Ngoại lệ:
        HeaderError: Khi khóa bắt buộc bị lặp hoặc value không phải str.
    """
    if not raw_properties:
        return {}

    items = (
        raw_properties.items()
        if isinstance(raw_properties, Mapping)
        else raw_properties
    )

    result: dict[str, str] = {}
    for key, value in items:
        if key in REQUIRED_USER_PROPERTIES and key in result:
            raise HeaderError(f"User Property bị lặp: {key}")
        if not isinstance(value, str):
            raise HeaderError(f"User Property {key!r} phải là chuỗi")
        result[key] = value
    return result


def build_headers(
    secret: bytes,
    topic: str,
    payload: bytes | str,
    correlation_id: Optional[str] = None,
    ts_ms: Optional[int] = None,
) -> tuple[dict[str, str], str, int]:
    """Tạo đầy đủ User Properties cho một message.

    Tham số:
        secret: Khóa HMAC của thiết bị.
        topic: Topic sẽ publish.
        payload: Payload chính xác sẽ gửi lên broker.
        correlation_id: Bỏ trống để sinh UUID mới; truyền vào khi cần dùng
            chung ID với lệnh/phản hồi.
        ts_ms: Bỏ trống để lấy thời gian hiện tại.

    Trả về:
        Tuple (headers, correlation_id, ts_ms).

    Ngoại lệ:
        SignatureError: Nếu không ký được (secret rỗng, payload sai kiểu).
    """
    cid = correlation_id or new_correlation_id()
    timestamp = int(ts_ms) if ts_ms is not None else now_ms()
    signature = sign_message(secret, topic, cid, timestamp, payload)
    headers = {
        USER_PROP_CORRELATION_ID: cid,
        USER_PROP_TS_MS: str(timestamp),
        USER_PROP_SIGNATURE: signature,
    }
    return headers, cid, timestamp


def verify_envelope(
    secret: bytes,
    topic: str,
    payload: bytes | str,
    raw_properties: Optional[
        Mapping[str, str] | Iterable[tuple[str, str]]
    ],
    replay_guard: Optional[ReplayGuard] = None,
    enforce_timestamp: bool = True,
) -> tuple[str, int, dict[str, str]]:
    """Xác thực header + chữ ký + (tùy chọn) chống replay.

    Tham số:
        secret: Khóa HMAC của thiết bị.
        topic, payload: Dữ liệu nhận từ broker.
        raw_properties: UserProperty lấy từ msg.properties.
        replay_guard: Nếu có, kiểm tra và ghi nhận correlation_id.
        enforce_timestamp: True với command/telemetry; False với status/LWT
            vì Will message được ký lúc CONNECT nên ts_ms có thể đã cũ.

    Trả về:
        Tuple (correlation_id, ts_ms, headers).

    Ngoại lệ:
        HeaderError: Thiếu/sai/trùng header bắt buộc.
        SignatureError: Chữ ký không hợp lệ.
        ReplayError: Timestamp lệch cửa sổ hoặc correlation_id đã dùng.
    """
    headers = normalize_user_properties(raw_properties)

    missing = [name for name in REQUIRED_USER_PROPERTIES if name not in headers]
    if missing:
        raise HeaderError(f"Thiếu User Property bắt buộc: {', '.join(missing)}")

    cid = headers[USER_PROP_CORRELATION_ID]
    if not cid:
        raise HeaderError("correlation_id rỗng")

    try:
        timestamp = int(headers[USER_PROP_TS_MS])
    except (TypeError, ValueError) as exc:
        raise HeaderError("ts_ms không phải số nguyên") from exc

    if timestamp < 0:
        raise HeaderError("ts_ms không được âm")

    # Xác thực chữ ký trước khi ghi nhận replay: bản tin giả mạo không được
    # phép chiếm chỗ correlation_id trong bộ nhớ chống replay.
    if not verify_message(
        secret,
        topic,
        cid,
        timestamp,
        payload,
        headers[USER_PROP_SIGNATURE],
    ):
        raise SignatureError("Chữ ký HMAC-SHA256 không hợp lệ")

    if replay_guard is not None and enforce_timestamp:
        replay_guard.check_and_record(cid, timestamp)

    return cid, timestamp, headers
