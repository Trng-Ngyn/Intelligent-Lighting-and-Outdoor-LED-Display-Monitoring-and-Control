"""Unit test cho topic northbound của Phương án C.

Chạy:
    python -m unittest discover -s tests -p "test_*.py" -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from iot_protocol.northbound_topics import (
    NORTHBOUND_CATEGORIES,
    ParsedNorthboundTopic,
    northbound_site_wildcard,
    northbound_tenant_wildcard,
    northbound_topic,
    parse_northbound_topic,
)
from iot_protocol.topics import TopicError


class NorthboundTopicTests(unittest.TestCase):
    """Kiểm tra ghép/phân tích topic gateway ↔ cloud."""

    def test_build_all_categories(self) -> None:
        for category in sorted(NORTHBOUND_CATEGORIES):
            self.assertEqual(
                northbound_topic("t1", "s01", "gw-001", category),
                f"pccom/v1/t1/s01/gw-001/{category}",
            )

    def test_build_known_examples(self) -> None:
        self.assertEqual(
            northbound_topic("t1", "s01", "gw-001", "telemetry"),
            "pccom/v1/t1/s01/gw-001/telemetry",
        )
        self.assertEqual(
            northbound_topic("t1", "s01", "gw-001", "cmd"),
            "pccom/v1/t1/s01/gw-001/cmd",
        )
        self.assertEqual(
            northbound_topic("t1", "s01", "gw-001", "status"),
            "pccom/v1/t1/s01/gw-001/status",
        )

    def test_wildcards_use_single_level_plus(self) -> None:
        self.assertEqual(
            northbound_site_wildcard("t1", "s01", "telemetry"),
            "pccom/v1/t1/s01/+/telemetry",
        )
        self.assertEqual(
            northbound_tenant_wildcard("t1", "alerts"),
            "pccom/v1/t1/+/+/alerts",
        )
        for topic in (
            northbound_site_wildcard("t1", "s01", "status"),
            northbound_tenant_wildcard("t1", "cmd"),
        ):
            self.assertNotIn("#", topic)

    def test_parse_topic(self) -> None:
        parsed = parse_northbound_topic("pccom/v1/t1/s01/gw-001/telemetry")
        self.assertEqual(
            parsed,
            ParsedNorthboundTopic(
                tenant_id="t1",
                site_id="s01",
                gateway_id="gw-001",
                category="telemetry",
            ),
        )

    def test_reject_invalid_structure(self) -> None:
        for topic in (
            "pccom/v1/t1/s01/gw-001",
            "pccom/v1/t1/s01/gw-001/telemetry/extra",
            "other/v1/t1/s01/gw-001/telemetry",
            "pccom/v2/t1/s01/gw-001/telemetry",
            "pccom/v1/t1/s01/gw-001/+/telemetry",
        ):
            with self.assertRaises(TopicError):
                parse_northbound_topic(topic)

    def test_reject_invalid_segments_and_category(self) -> None:
        with self.assertRaises(TopicError):
            northbound_topic("t/1", "s01", "gw-001", "telemetry")
        with self.assertRaises(TopicError):
            northbound_topic("t1", "s01", "gw-001", "unknown")
        with self.assertRaises(TopicError):
            northbound_topic("t1", "s01", "gw#001", "telemetry")


if __name__ == "__main__":
    unittest.main()
