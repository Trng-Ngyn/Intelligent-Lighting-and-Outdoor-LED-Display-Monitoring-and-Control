"""Unit test cho canonical envelope và khóa gateway northbound."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from iot_protocol.northbound_payload import (
    NorthboundPayloadError,
    build_envelope,
    command_target,
    derive_gateway_key,
    encode_envelope,
    normalize_ack_status,
    parse_envelope,
)


class NorthboundEnvelopeTests(unittest.TestCase):
    """Kiểm tra envelope canonical và mapping trạng thái ack."""

    def test_gateway_key_is_deterministic_and_scoped(self) -> None:
        first = derive_gateway_key("master-secret", "t1", "s01", "gw-001")
        second = derive_gateway_key("master-secret", "t1", "s01", "gw-001")
        other = derive_gateway_key("master-secret", "t1", "s02", "gw-002")
        self.assertEqual(first, second)
        self.assertNotEqual(first, other)

    def test_build_and_parse_roundtrip(self) -> None:
        envelope = build_envelope(
            tenant_id="t1",
            site_id="s01",
            gateway_id="gw-001",
            source_site_id="SITE_01",
            device_type="light",
            device_id="LGT_NODE_001",
            category="telemetry",
            data={"asset_id": "LGT_NODE_001", "source_time": 100, "sequence": 7},
        )
        parsed = parse_envelope(encode_envelope(envelope))
        self.assertEqual(parsed["tenant_id"], "t1")
        self.assertEqual(parsed["source_site_id"], "SITE_01")
        self.assertEqual(parsed["device_id"], "LGT_NODE_001")
        self.assertEqual(parsed["category"], "telemetry")
        self.assertEqual(parsed["source_time"], 100)

    def test_parse_rejects_missing_fields(self) -> None:
        with self.assertRaises(NorthboundPayloadError):
            parse_envelope('{"tenant_id":"t1"}')

    def test_command_target_flat_and_nested(self) -> None:
        flat = {
            "source_site_id": "SITE_01",
            "device_type": "light",
            "device_id": "LGT_NODE_001",
        }
        self.assertEqual(
            command_target(flat),
            ("SITE_01", "light", "LGT_NODE_001"),
        )
        nested = {
            "source_site_id": "SITE_01",
            "target": {
                "asset_id": "LGT_NODE_002",
                "device_type": "light",
            },
        }
        self.assertEqual(
            command_target(nested),
            ("SITE_01", "light", "LGT_NODE_002"),
        )

    def test_normalize_ack_status(self) -> None:
        self.assertEqual(normalize_ack_status("EXECUTED"), "executed")
        self.assertEqual(normalize_ack_status("REJECTED"), "rejected")
        self.assertEqual(normalize_ack_status("expired"), "expired")
        self.assertEqual(normalize_ack_status(None), "unknown")


if __name__ == "__main__":
    unittest.main()
