"""Helper tạo MQTT 5 Properties cho paho-mqtt 2.x.

Tách riêng để các module không phải lặp lại cấu hình Content Type, Message
Expiry Interval, Correlation Data, Response Topic và Will Delay Interval.

Vị trí trong luồng: được Simulator và Mock Cloud dùng ngay trước khi publish
hoặc CONNECT. Xem docs/specifications/MQTT5_COMMUNICATION_PROTOCOL.md.
"""

from __future__ import annotations

from typing import Mapping, Optional

from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties

CONTENT_TYPE_JSON = "application/json"
CONTENT_TYPE_TEXT = "text/plain; charset=utf-8"

# Lý do có Message Expiry Interval: lệnh dim chỉ có ý nghĩa trong thời gian
# ngắn. Nếu broker giữ lệnh quá lâu (mất mạng, hàng đợi), thiết bị không được
# thực thi lệnh cũ. Giá trị 60s khớp với trường expires_at hiện có của payload.
COMMAND_MESSAGE_EXPIRY_SEC = 60

# Will Delay = 0: phát hiện mất kết nối nhanh nhất có thể. Yêu cầu nghiệp vụ
# là biết thiết bị offline trong vòng 30 giây, nên không trì hoãn thêm.
WILL_DELAY_INTERVAL_SEC = 0


def make_publish_properties(
    user_properties: Mapping[str, str],
    content_type: str = CONTENT_TYPE_JSON,
    message_expiry_interval: Optional[int] = None,
    correlation_data: Optional[bytes] = None,
    response_topic: Optional[str] = None,
) -> Properties:
    """Tạo Properties cho gói PUBLISH.

    Tham số:
        user_properties: Dict correlation_id/ts_ms/signature.
        content_type: MIME type của payload.
        message_expiry_interval: Giây; dùng cho lệnh dim.
        correlation_data: Bytes của correlation_id (chuẩn MQTT 5).
        response_topic: Topic phản hồi mong muốn (chuẩn MQTT 5).

    Trả về:
        paho Properties đã gắn PacketTypes.PUBLISH.
    """
    props = Properties(PacketTypes.PUBLISH)
    props.UserProperty = list(user_properties.items())
    props.ContentType = content_type
    if message_expiry_interval is not None:
        props.MessageExpiryInterval = int(message_expiry_interval)
    if correlation_data is not None:
        props.CorrelationData = correlation_data
    if response_topic is not None:
        props.ResponseTopic = response_topic
    return props


def make_will_properties(
    user_properties: Mapping[str, str],
    content_type: str = CONTENT_TYPE_TEXT,
) -> Properties:
    """Tạo Properties cho Will message.

    Will Delay Interval = 0 và retain=true được đặt ở phía client.will_set().
    PayloadFormatIndicator = 1 (UTF-8) vì payload status là "online"/"offline".
    """
    props = Properties(PacketTypes.WILLMESSAGE)
    props.UserProperty = list(user_properties.items())
    props.ContentType = content_type
    props.PayloadFormatIndicator = 1
    props.WillDelayInterval = WILL_DELAY_INTERVAL_SEC
    return props


def make_connect_properties(session_expiry_interval: int = 0) -> Properties:
    """Tạo Properties cho gói CONNECT.

    Session Expiry Interval = 0: không giữ session sau khi ngắt; LWT và trạng
    thái retained đã đủ để Cloud phát hiện offline. Điều này tránh hàng đợi
    lệnh cũ cho thiết bị đã chết.
    """
    props = Properties(PacketTypes.CONNECT)
    props.SessionExpiryInterval = int(session_expiry_interval)
    return props
