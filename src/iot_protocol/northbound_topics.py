"""Quy tắc topic northbound cho Phương án C.

Luồng: thiết bị ↔ gateway dùng taxonomy IoT hiện có; gateway ↔ cloud dùng
namespace tenant-first của Tech Lead:

    pccom/v1/{tenant_id}/{site_id}/{gateway_id}/{category}

Các category baseline gồm telemetry, cmd, ack, status, alerts và receipt tùy
chọn. Module này chỉ ghép/phân tích topic; bridge chịu trách nhiệm map payload
và trạng thái giữa hai lớp.
"""

from __future__ import annotations

from dataclasses import dataclass

from .topics import TOPIC_VERSION, TopicError, validate_segment

NORTHBOUND_PREFIX = "pccom"

# Từ vựng category đóng để Cloud/Gateway không tự sinh nhánh topic ngoài đặc tả.
NORTHBOUND_CATEGORIES = frozenset(
    {"telemetry", "cmd", "ack", "status", "alerts", "receipt"}
)


def validate_category(category: str) -> str:
    """Kiểm tra category northbound thuộc từ vựng đã chốt."""
    validate_segment(category, "category")
    if category not in NORTHBOUND_CATEGORIES:
        allowed = ", ".join(sorted(NORTHBOUND_CATEGORIES))
        raise TopicError(
            f"category northbound không được hỗ trợ: {category!r}. "
            f"Cho phép: {allowed}"
        )
    return category


def northbound_topic(
    tenant_id: str,
    site_id: str,
    gateway_id: str,
    category: str,
) -> str:
    """Ghép topic gateway ↔ cloud cho một tenant/site/gateway.

    Ví dụ:
        northbound_topic("t1", "s01", "gw-001", "telemetry")
        -> "pccom/v1/t1/s01/gw-001/telemetry"
    """
    tenant = validate_segment(tenant_id, "tenant_id")
    site = validate_segment(site_id, "site_id")
    gateway = validate_segment(gateway_id, "gateway_id")
    cat = validate_category(category)
    return f"{NORTHBOUND_PREFIX}/{TOPIC_VERSION}/{tenant}/{site}/{gateway}/{cat}"


def northbound_site_wildcard(
    tenant_id: str,
    site_id: str,
    category: str,
) -> str:
    """Wildcard cho mọi gateway trong một tenant/site."""
    tenant = validate_segment(tenant_id, "tenant_id")
    site = validate_segment(site_id, "site_id")
    cat = validate_category(category)
    return f"{NORTHBOUND_PREFIX}/{TOPIC_VERSION}/{tenant}/{site}/+/{cat}"


def northbound_tenant_wildcard(
    tenant_id: str,
    category: str,
) -> str:
    """Wildcard cho mọi site/gateway trong một tenant."""
    tenant = validate_segment(tenant_id, "tenant_id")
    cat = validate_category(category)
    return f"{NORTHBOUND_PREFIX}/{TOPIC_VERSION}/{tenant}/+/+/{cat}"


@dataclass(frozen=True)
class ParsedNorthboundTopic:
    """Kết quả phân tích một topic northbound đã được xác thực cấu trúc."""

    tenant_id: str
    site_id: str
    gateway_id: str
    category: str


def parse_northbound_topic(topic: str) -> ParsedNorthboundTopic:
    """Phân tích topic northbound thực tế (không chứa wildcard).

    Ngoại lệ:
        TopicError: Nếu sai prefix/version/số segment/category hoặc có wildcard.
    """
    parts = topic.split("/")
    if len(parts) != 6 or parts[0] != NORTHBOUND_PREFIX:
        raise TopicError(f"Topic northbound sai cấu trúc: {topic!r}")

    if parts[1] != TOPIC_VERSION:
        raise TopicError(f"Topic northbound sai version: {topic!r}")

    tenant_id = validate_segment(parts[2], "tenant_id")
    site_id = validate_segment(parts[3], "site_id")
    gateway_id = validate_segment(parts[4], "gateway_id")
    category = validate_category(parts[5])

    return ParsedNorthboundTopic(
        tenant_id=tenant_id,
        site_id=site_id,
        gateway_id=gateway_id,
        category=category,
    )
