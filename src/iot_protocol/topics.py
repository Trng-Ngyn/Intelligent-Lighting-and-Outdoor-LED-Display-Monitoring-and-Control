"""Quy tắc topic MQTT 5 dùng chung cho Simulator, Broker và Cloud.

Vị trí trong luồng: Simulator -> Broker -> Cloud (và ngược lại). Mọi module
publish/subscribe đều phải dùng các hàm trong file này thay vì tự ghép chuỗi,
để bảo đảm taxonomy và quy tắc wildcard luôn nhất quán.

Taxonomy v1:
- telemetry/v1/{site_id}/{device_type}/{device_id}
- commands/v1/{site_id}/{device_type}/{device_id}/dim
- commands/v1/{site_id}/{device_type}/{device_id}/dim/result
- status/v1/{site_id}/{device_type}/{device_id}
- alerts/v1/{site_id}/{device_type}/{device_id}

Xem docs/specifications/MQTT5_COMMUNICATION_PROTOCOL.md để biết QoS/retain,
hướng publish/subscribe và ACL mẫu.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

TOPIC_VERSION = "v1"

# Chỉ cho phép chữ, số, gạch dưới và gạch ngang. Cố ý loại bỏ '/', '+', '#',
# khoảng trắng và ký tự điều khiển vì chúng làm thay đổi cấu trúc topic hoặc
# tạo wildcard ngoài ý muốn.
SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# Từ vựng device_type được phép xuất hiện trong segment thứ tư của topic.
ALLOWED_DEVICE_TYPES = frozenset({"light", "led_display", "gateway"})


class TopicError(ValueError):
    """Lỗi khi tên segment hoặc topic không đúng đặc tả."""


def validate_segment(value: str, name: str) -> str:
    """Kiểm tra một segment topic.

    Tham số:
        value: Giá trị cần kiểm tra (site_id, device_type, device_id).
        name: Tên trường dùng trong thông báo lỗi.

    Trả về:
        Chính giá trị đầu vào sau khi kiểm tra.

    Ngoại lệ:
        TopicError: Nếu giá trị rỗng, quá 64 ký tự hoặc chứa ký tự cấm.
    """
    if not isinstance(value, str) or not SEGMENT_PATTERN.fullmatch(value):
        raise TopicError(
            f"{name} không hợp lệ: {value!r}. "
            "Chỉ cho phép [A-Za-z0-9_-], độ dài 1-64."
        )
    return value


def validate_device_type(device_type: str) -> str:
    """Kiểm tra device_type thuộc từ vựng đã chốt.

    Lý do dùng từ vựng đóng: Cloud đặt wildcard theo device_type và ACL cũng
    dựa vào segment này; nếu cho phép giá trị tùy ý thì việc phân quyền và
    thống kê sẽ không kiểm soát được.
    """
    validate_segment(device_type, "device_type")
    if device_type not in ALLOWED_DEVICE_TYPES:
        allowed = ", ".join(sorted(ALLOWED_DEVICE_TYPES))
        raise TopicError(
            f"device_type không được hỗ trợ: {device_type!r}. Cho phép: {allowed}"
        )
    return device_type


def _prefix(category: str, site_id: str, device_type: str, device_id: str) -> str:
    """Ghép phần đầu chung của mọi topic v1."""
    site = validate_segment(site_id, "site_id")
    dtype = validate_device_type(device_type)
    did = validate_segment(device_id, "device_id")
    return f"{category}/{TOPIC_VERSION}/{site}/{dtype}/{did}"


def telemetry_topic(site_id: str, device_type: str, device_id: str) -> str:
    """Topic telemetry do thiết bị publish, Cloud subscribe."""
    return _prefix("telemetry", site_id, device_type, device_id)


def command_dim_topic(site_id: str, device_type: str, device_id: str) -> str:
    """Topic lệnh dim do Cloud publish, thiết bị subscribe."""
    return f"{_prefix('commands', site_id, device_type, device_id)}/dim"


def command_result_topic(site_id: str, device_type: str, device_id: str) -> str:
    """Topic phản hồi lệnh, dùng chung correlation_id với lệnh gốc.

    Phản hồi nằm dưới nhánh commands để giữ mọi bản tin điều khiển trong cùng
    một namespace, thuận tiện cho ACL và truy vết.
    """
    return f"{command_dim_topic(site_id, device_type, device_id)}/result"


def status_topic(site_id: str, device_type: str, device_id: str) -> str:
    """Topic trạng thái online/offline (retained, QoS 1, có LWT)."""
    return _prefix("status", site_id, device_type, device_id)


def alerts_topic(site_id: str, device_type: str, device_id: str) -> str:
    """Topic cảnh báo bảo mật/vận hành do thiết bị hoặc Cloud publish."""
    return _prefix("alerts", site_id, device_type, device_id)


def telemetry_wildcard() -> str:
    """Wildcard Cloud dùng để nhận telemetry của mọi thiết bị.

    Lý do dùng '+' thay vì '#': '+' khớp đúng một segment, nhờ đó Cloud không
    vô tình subscribe cả các nhánh con như commands/alerts.
    """
    return f"telemetry/{TOPIC_VERSION}/+/+/+"


def status_wildcard() -> str:
    """Wildcard Cloud dùng để theo dõi online/offline của mọi thiết bị."""
    return f"status/{TOPIC_VERSION}/+/+/+"


def alerts_wildcard() -> str:
    """Wildcard Cloud dùng để nhận mọi cảnh báo."""
    return f"alerts/{TOPIC_VERSION}/+/+/+"


def command_dim_wildcard() -> str:
    """Wildcard Cloud dùng để theo dõi toàn bộ lệnh dim (audit/debug)."""
    return f"commands/{TOPIC_VERSION}/+/+/+/dim"


def command_result_wildcard() -> str:
    """Wildcard Cloud dùng để nhận phản hồi lệnh của mọi thiết bị."""
    return f"commands/{TOPIC_VERSION}/+/+/+/dim/result"


@dataclass(frozen=True)
class ParsedTopic:
    """Kết quả phân tích một topic v1 đã được xác thực cấu trúc."""

    category: str
    site_id: str
    device_type: str
    device_id: str

    @property
    def is_command(self) -> bool:
        """True nếu đây là topic lệnh dim."""
        return self.category == "command"

    @property
    def is_command_result(self) -> bool:
        """True nếu đây là topic phản hồi lệnh."""
        return self.category == "command_result"


def parse_topic(topic: str) -> ParsedTopic:
    """Phân tích topic thực tế (không chứa wildcard) thành các segment.

    Tham số:
        topic: Chuỗi topic nhận từ broker.

    Trả về:
        ParsedTopic với category là telemetry/status/alerts/command/command_result.

    Ngoại lệ:
        TopicError: Nếu topic sai số segment, sai version hoặc chứa wildcard.
    """
    parts = topic.split("/")
    if not parts or parts[0] not in {"telemetry", "commands", "status", "alerts"}:
        raise TopicError(f"Không nhận diện được nhóm topic: {topic!r}")

    if len(parts) < 5 or parts[1] != TOPIC_VERSION:
        raise TopicError(f"Topic sai cấu trúc hoặc version: {topic!r}")

    category_name = parts[0]
    site_id = validate_segment(parts[2], "site_id")
    device_type = validate_device_type(parts[3])
    device_id = validate_segment(parts[4], "device_id")

    if category_name in {"telemetry", "status", "alerts"}:
        if len(parts) != 5:
            raise TopicError(f"Topic {category_name} phải có đúng 5 segment: {topic!r}")
        category = category_name
    elif len(parts) == 6 and parts[5] == "dim":
        category = "command"
    elif len(parts) == 7 and parts[5] == "dim" and parts[6] == "result":
        category = "command_result"
    else:
        raise TopicError(f"Topic commands không hợp lệ: {topic!r}")

    return ParsedTopic(
        category=category,
        site_id=site_id,
        device_type=device_type,
        device_id=device_id,
    )
