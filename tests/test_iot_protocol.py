"""Unit test cho topic taxonomy, chữ ký và chống replay.

Chạy:
    python -m unittest discover -s tests -p "test_*.py" -v

Các test này không cần broker/mạng; chúng bảo vệ phần giao thức thuần Python
trước khi chạy kiểm thử end-to-end.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from iot_protocol.headers import (
    HeaderError,
    build_headers,
    normalize_user_properties,
    verify_envelope,
)
from iot_protocol.signing import (
    ReplayError,
    ReplayGuard,
    SignatureError,
    canonical_string,
    derive_device_key,
    sign_message,
    verify_message,
)
from iot_protocol.topics import (
    TopicError,
    alerts_topic,
    alerts_wildcard,
    command_dim_topic,
    command_dim_wildcard,
    command_result_topic,
    command_result_wildcard,
    parse_topic,
    status_topic,
    status_wildcard,
    telemetry_topic,
    telemetry_wildcard,
    validate_segment,
)


class TopicTests(unittest.TestCase):
    """Kiểm tra ghép/phân tích topic và quy tắc segment."""

    def test_build_all_topics(self) -> None:
        self.assertEqual(
            telemetry_topic("SITE_01", "light", "LGT_NODE_001"),
            "telemetry/v1/SITE_01/light/LGT_NODE_001",
        )
        self.assertEqual(
            command_dim_topic("SITE_01", "light", "LGT_NODE_001"),
            "commands/v1/SITE_01/light/LGT_NODE_001/dim",
        )
        self.assertEqual(
            command_result_topic("SITE_01", "light", "LGT_NODE_001"),
            "commands/v1/SITE_01/light/LGT_NODE_001/dim/result",
        )
        self.assertEqual(
            status_topic("SITE_01", "light", "LGT_NODE_001"),
            "status/v1/SITE_01/light/LGT_NODE_001",
        )
        self.assertEqual(
            alerts_topic("SITE_01", "light", "LGT_NODE_001"),
            "alerts/v1/SITE_01/light/LGT_NODE_001",
        )

    def test_wildcards_use_single_level_plus(self) -> None:
        self.assertEqual(telemetry_wildcard(), "telemetry/v1/+/+/+")
        self.assertEqual(status_wildcard(), "status/v1/+/+/+")
        self.assertEqual(alerts_wildcard(), "alerts/v1/+/+/+")
        self.assertEqual(
            command_dim_wildcard(),
            "commands/v1/+/+/+/dim",
        )
        self.assertEqual(
            command_result_wildcard(),
            "commands/v1/+/+/+/dim/result",
        )
        for topic in (
            telemetry_wildcard(),
            status_wildcard(),
            alerts_wildcard(),
            command_dim_wildcard(),
            command_result_wildcard(),
        ):
            self.assertNotIn("#", topic)

    def test_reject_invalid_segments(self) -> None:
        for bad in ["", "a/b", "a+b", "a#b", "a b", "a\nb", "x" * 65]:
            with self.assertRaises(TopicError):
                validate_segment(bad, "site_id")

    def test_reject_unknown_device_type(self) -> None:
        with self.assertRaises(TopicError):
            telemetry_topic("SITE_01", "camera", "CAM_001")

    def test_parse_topics(self) -> None:
        parsed = parse_topic("telemetry/v1/SITE_01/light/LGT_NODE_001")
        self.assertEqual(parsed.category, "telemetry")
        self.assertEqual(parsed.site_id, "SITE_01")
        self.assertEqual(parsed.device_type, "light")
        self.assertEqual(parsed.device_id, "LGT_NODE_001")

        parsed = parse_topic("commands/v1/SITE_01/light/LGT_NODE_001/dim")
        self.assertTrue(parsed.is_command)

        parsed = parse_topic(
            "commands/v1/SITE_01/light/LGT_NODE_001/dim/result"
        )
        self.assertTrue(parsed.is_command_result)

    def test_parse_rejects_wildcard_and_wrong_version(self) -> None:
        with self.assertRaises(TopicError):
            parse_topic("telemetry/v1/+/+/+")
        with self.assertRaises(TopicError):
            parse_topic("telemetry/v2/SITE_01/light/LGT_NODE_001")
        with self.assertRaises(TopicError):
            parse_topic("commands/v1/SITE_01/light/LGT_NODE_001/dim/extra")


class SigningTests(unittest.TestCase):
    """Kiểm tra canonical string, HMAC và dẫn xuất khóa."""

    def test_canonical_string_shape(self) -> None:
        canonical = canonical_string(
            "telemetry/v1/SITE_01/light/LGT_NODE_001",
            "cid-1",
            1700000000000,
            '{"a":1}',
        )
        self.assertEqual(
            canonical,
            (
                "v1\n"
                "telemetry/v1/SITE_01/light/LGT_NODE_001\n"
                "cid-1\n"
                "1700000000000\n"
                '{"a":1}'
            ).encode("utf-8"),
        )

    def test_sign_and_verify(self) -> None:
        secret = derive_device_key(
            "master-secret-for-test",
            "SITE_01",
            "light",
            "LGT_NODE_001",
        )
        signature = sign_message(
            secret,
            "telemetry/v1/SITE_01/light/LGT_NODE_001",
            "cid-1",
            1700000000000,
            '{"a":1}',
        )
        self.assertTrue(
            verify_message(
                secret,
                "telemetry/v1/SITE_01/light/LGT_NODE_001",
                "cid-1",
                1700000000000,
                '{"a":1}',
                signature,
            )
        )
        self.assertFalse(
            verify_message(
                secret,
                "telemetry/v1/SITE_01/light/LGT_NODE_001",
                "cid-1",
                1700000000000,
                '{"a":2}',
                signature,
            )
        )

    def test_device_keys_are_distinct(self) -> None:
        secret_a = derive_device_key("master", "SITE_01", "light", "LGT_001")
        secret_b = derive_device_key("master", "SITE_01", "light", "LGT_002")
        self.assertNotEqual(secret_a, secret_b)

    def test_invalid_signature_format(self) -> None:
        secret = b"secret"
        self.assertFalse(
            verify_message(secret, "t", "c", 1, "p", "not-hex")
        )
        self.assertFalse(
            verify_message(secret, "t", "c", 1, "p", "a" * 63)
        )


class ReplayGuardTests(unittest.TestCase):
    """Kiểm tra cửa sổ thời gian và phát hiện correlation_id lặp."""

    def setUp(self) -> None:
        self.now = 1_000_000
        self.guard = ReplayGuard(
            window_ms=1000,
            future_skew_ms=100,
            clock_ms=lambda: self.now,
        )

    def test_accepts_fresh_and_rejects_duplicate(self) -> None:
        self.guard.check_and_record("cid-1", self.now - 10)
        with self.assertRaises(ReplayError):
            self.guard.check_and_record("cid-1", self.now - 9)

    def test_rejects_too_old(self) -> None:
        with self.assertRaises(ReplayError):
            self.guard.check_and_record("cid-old", self.now - 1001)

    def test_rejects_future_beyond_skew(self) -> None:
        with self.assertRaises(ReplayError):
            self.guard.check_and_record("cid-future", self.now + 101)

    def test_prunes_old_ids(self) -> None:
        self.guard.check_and_record("cid-1", self.now - 900)
        self.now += 200
        self.guard.check_and_record("cid-2", self.now)
        self.assertEqual(len(self.guard), 1)


class HeaderTests(unittest.TestCase):
    """Kiểm tra build/verify User Properties."""

    def setUp(self) -> None:
        self.secret = derive_device_key(
            "master-secret-for-test",
            "SITE_01",
            "light",
            "LGT_NODE_001",
        )
        self.topic = "commands/v1/SITE_01/light/LGT_NODE_001/dim"
        self.payload = '{"action":"DIM","requested_value":50}'

    def test_build_and_verify(self) -> None:
        headers, cid, ts_ms = build_headers(
            self.secret,
            self.topic,
            self.payload,
            ts_ms=1_000_000,
        )
        verified_cid, verified_ts, _ = verify_envelope(
            self.secret,
            self.topic,
            self.payload,
            headers,
        )
        self.assertEqual(verified_cid, cid)
        self.assertEqual(verified_ts, ts_ms)

    def test_missing_header(self) -> None:
        headers, _, _ = build_headers(
            self.secret,
            self.topic,
            self.payload,
            ts_ms=1_000_000,
        )
        del headers["signature"]
        with self.assertRaises(HeaderError):
            verify_envelope(
                self.secret,
                self.topic,
                self.payload,
                headers,
            )

    def test_duplicate_required_header(self) -> None:
        headers, _, _ = build_headers(
            self.secret,
            self.topic,
            self.payload,
            ts_ms=1_000_000,
        )
        raw = list(headers.items()) + [("correlation_id", "other")]
        with self.assertRaises(HeaderError):
            normalize_user_properties(raw)

    def test_bad_signature(self) -> None:
        headers, _, _ = build_headers(
            self.secret,
            self.topic,
            self.payload,
            ts_ms=1_000_000,
        )
        with self.assertRaises(SignatureError):
            verify_envelope(
                self.secret,
                self.topic,
                self.payload + "x",
                headers,
            )

    def test_replay_detected(self) -> None:
        now = 1_000_000
        guard = ReplayGuard(window_ms=1000, clock_ms=lambda: now)
        headers, _, _ = build_headers(
            self.secret,
            self.topic,
            self.payload,
            ts_ms=now,
        )
        verify_envelope(
            self.secret,
            self.topic,
            self.payload,
            headers,
            replay_guard=guard,
        )
        with self.assertRaises(ReplayError):
            verify_envelope(
                self.secret,
                self.topic,
                self.payload,
                headers,
                replay_guard=guard,
            )


if __name__ == "__main__":
    unittest.main()
