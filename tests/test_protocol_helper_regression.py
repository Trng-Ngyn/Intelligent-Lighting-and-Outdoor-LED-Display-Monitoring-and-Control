"""AUTO-G1-005 - Regression tests cho protocol helper (iot_protocol).

Phạm vi: chỉ bổ sung các assertion CHƯA có trong tests/test_iot_protocol.py,
tests/test_northbound_payload.py và tests/test_northbound_topics.py.

Test Oracle (nguồn):
- O-HDR  : docstring + code của src/iot_protocol/headers.py (verify_envelope,
           normalize_user_properties, build_headers).
- O-SIG  : docstring + code của src/iot_protocol/signing.py.
- O-NBP  : docstring + code của src/iot_protocol/northbound_payload.py.
Các test có tên bắt đầu bằng ``test_characterize_`` ghi lại hành vi quan sát được
của implementation hiện tại; chúng KHÔNG phải acceptance criteria và mặc định bị
skip khi không bật opt-in ``PCCOM_RUN_CHARACTERIZATION=1``. Yêu cầu CTL/SEC chưa
quy định kỳ vọng ở mức này nên oracle được ghi là "chưa xác lập".

Giới hạn: đây là unit test thuần Python, không broker, không mạng, không thiết bị.
Kết quả không chứng minh dispatch hay phản hồi phần cứng.
"""

from __future__ import annotations

import json
import os
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from iot_protocol.headers import (
    HeaderError,
    build_headers,
    normalize_user_properties,
    verify_envelope,
)
from iot_protocol.northbound_payload import (
    ACK_STATUS_MAP,
    NorthboundPayloadError,
    build_envelope,
    command_target,
    derive_gateway_key,
    encode_envelope,
    envelope_device_key,
    normalize_ack_status,
    parse_envelope,
)
from iot_protocol.northbound_topics import northbound_topic
from iot_protocol.signing import (
    ReplayError,
    ReplayGuard,
    SignatureError,
    canonical_string,
    derive_device_key,
    now_ms,
    sign_message,
    verify_message,
)
from iot_protocol.topics import TopicError, validate_segment

NOW = 1_700_000_000_000
DEVICE_TOPIC = "commands/v1/SITE_01/light/LGT_NODE_001/dim"
OTHER_DEVICE_TOPIC = "commands/v1/SITE_01/light/LGT_NODE_002/dim"
PAYLOAD = '{"action":"DIM","requested_value":50}'


def _flip_last_hex(signature: str) -> str:
    """Tạo chữ ký cùng độ dài nhưng sai một ký tự cuối."""
    return signature[:-1] + ("0" if signature[-1] != "0" else "1")


class HeaderNormalizationRegressionTests(unittest.TestCase):
    """O-HDR: normalize_user_properties."""

    def test_empty_inputs_yield_empty_dict(self) -> None:
        for raw in (None, {}, []):
            with self.subTest(raw=raw):
                self.assertEqual(normalize_user_properties(raw), {})

    def test_mapping_and_pair_list_are_equivalent(self) -> None:
        pairs = [("correlation_id", "c1"), ("ts_ms", "5"), ("signature", "s")]
        self.assertEqual(
            normalize_user_properties(pairs),
            normalize_user_properties(dict(pairs)),
        )

    def test_non_string_value_is_rejected(self) -> None:
        for value in (1, None, b"x", ["a"]):
            with self.subTest(value=value):
                with self.assertRaises(HeaderError):
                    normalize_user_properties([("x-extra", value)])

    def test_every_required_key_rejects_duplicates(self) -> None:
        for key in ("correlation_id", "ts_ms", "signature"):
            with self.subTest(key=key):
                with self.assertRaises(HeaderError):
                    normalize_user_properties([(key, "a"), (key, "b")])

    @unittest.skipUnless(
        os.environ.get("PCCOM_RUN_CHARACTERIZATION") == "1",
        "Non-normative characterization; enable PCCOM_RUN_CHARACTERIZATION=1",
    )
    def test_characterize_repeated_optional_key_keeps_last_value(self) -> None:
        # Docstring chỉ yêu cầu khóa bắt buộc xuất hiện một lần; hành vi với khóa
        # tùy chọn không được đặc tả nên chỉ ghi lại hiện trạng.
        self.assertEqual(
            normalize_user_properties([("x", "1"), ("x", "2")]),
            {"x": "2"},
        )


class BuildHeadersRegressionTests(unittest.TestCase):
    """O-HDR: build_headers."""

    def setUp(self) -> None:
        self.secret = derive_device_key(
            "master-secret-for-test", "SITE_01", "light", "LGT_NODE_001"
        )

    def test_supplied_correlation_id_and_ts_are_preserved(self) -> None:
        headers, cid, ts_ms = build_headers(
            self.secret, DEVICE_TOPIC, PAYLOAD, correlation_id="cid-fixed", ts_ms=NOW
        )
        self.assertEqual(cid, "cid-fixed")
        self.assertEqual(ts_ms, NOW)
        self.assertEqual(headers["correlation_id"], "cid-fixed")
        self.assertEqual(headers["ts_ms"], str(NOW))
        self.assertEqual(set(headers), {"correlation_id", "ts_ms", "signature"})
        self.assertRegex(headers["signature"], r"^[0-9a-f]{64}$")

    def test_zero_timestamp_is_not_replaced_by_clock(self) -> None:
        _, _, ts_ms = build_headers(self.secret, DEVICE_TOPIC, PAYLOAD, ts_ms=0)
        self.assertEqual(ts_ms, 0)

    def test_generated_correlation_id_is_uuid4_and_unique(self) -> None:
        before = now_ms()
        first, cid_a, ts_a = build_headers(self.secret, DEVICE_TOPIC, PAYLOAD)
        second, cid_b, _ = build_headers(self.secret, DEVICE_TOPIC, PAYLOAD, correlation_id="")
        after = now_ms()
        self.assertEqual(uuid.UUID(cid_a).version, 4)
        self.assertEqual(uuid.UUID(cid_b).version, 4)
        self.assertNotEqual(cid_a, cid_b)
        self.assertTrue(before <= ts_a <= after)
        self.assertEqual(first["correlation_id"], cid_a)
        self.assertEqual(second["correlation_id"], cid_b)

    def test_unsignable_inputs_raise_signature_error(self) -> None:
        with self.assertRaises(SignatureError):
            build_headers(b"", DEVICE_TOPIC, PAYLOAD, ts_ms=NOW)
        for bad_payload in (123, None, ["x"]):
            with self.subTest(payload=bad_payload):
                with self.assertRaises(SignatureError):
                    build_headers(self.secret, DEVICE_TOPIC, bad_payload, ts_ms=NOW)


class SigningInputRegressionTests(unittest.TestCase):
    """O-SIG: ràng buộc đầu vào của signing helper."""

    def test_empty_secret_is_rejected_everywhere(self) -> None:
        with self.assertRaises(SignatureError):
            derive_device_key("", "SITE_01", "light", "LGT_NODE_001")
        with self.assertRaises(SignatureError):
            sign_message(b"", "t", "c", 1, "p")

    def test_canonical_string_rejects_non_text_payload(self) -> None:
        for bad_payload in (123, None, ["x"], {"a": 1}):
            with self.subTest(payload=bad_payload):
                with self.assertRaises(SignatureError):
                    canonical_string("t", "c", 1, bad_payload)

    def test_signature_is_lowercase_hex_64(self) -> None:
        signature = sign_message(b"secret", "t", "c", 1, "p")
        self.assertRegex(signature, r"^[0-9a-f]{64}$")

    def test_str_bytes_and_bytearray_payload_sign_identically(self) -> None:
        text = '{"ten":"Đèn LED"}'
        expected = sign_message(b"secret", "t", "c", 1, text)
        self.assertEqual(sign_message(b"secret", "t", "c", 1, text.encode("utf-8")), expected)
        self.assertEqual(
            sign_message(b"secret", "t", "c", 1, bytearray(text.encode("utf-8"))),
            expected,
        )

    def test_malformed_signature_values_return_false(self) -> None:
        # Đủ 64 ký tự nhưng không phải hex; và các kiểu không phải str.
        for bad in ("g" * 64, "z" * 64, None, 123, b"a" * 64, ""):
            with self.subTest(signature=bad):
                self.assertFalse(verify_message(b"secret", "t", "c", 1, "p", bad))

    @unittest.skipUnless(
        os.environ.get("PCCOM_RUN_CHARACTERIZATION") == "1",
        "Non-normative characterization; enable PCCOM_RUN_CHARACTERIZATION=1",
    )
    def test_characterize_uppercase_hex_signature_is_accepted(self) -> None:
        signature = sign_message(b"secret", "t", "c", 1, "p")
        self.assertTrue(verify_message(b"secret", "t", "c", 1, "p", signature.upper()))


class EnvelopeVerificationRegressionTests(unittest.TestCase):
    """O-HDR: verify_envelope - scope, correlation, thứ tự kiểm tra, replay."""

    def setUp(self) -> None:
        self.now = NOW
        self.secret = derive_device_key(
            "master-secret-for-test", "SITE_01", "light", "LGT_NODE_001"
        )
        self.other_secret = derive_device_key(
            "master-secret-for-test", "SITE_01", "light", "LGT_NODE_002"
        )
        self.guard = ReplayGuard(window_ms=1000, future_skew_ms=100, clock_ms=lambda: self.now)
        self.headers, self.cid, self.ts_ms = build_headers(
            self.secret, DEVICE_TOPIC, PAYLOAD, correlation_id="cid-scope-1", ts_ms=self.now
        )

    def test_missing_properties_report_every_missing_name(self) -> None:
        with self.assertRaises(HeaderError) as ctx:
            verify_envelope(self.secret, DEVICE_TOPIC, PAYLOAD, None)
        for name in ("correlation_id", "ts_ms", "signature"):
            self.assertIn(name, str(ctx.exception))

    def test_empty_correlation_id_is_rejected(self) -> None:
        headers = dict(self.headers, correlation_id="")
        with self.assertRaises(HeaderError):
            verify_envelope(self.secret, DEVICE_TOPIC, PAYLOAD, headers)

    def test_non_integer_or_negative_timestamp_is_rejected(self) -> None:
        for bad_ts in ("abc", "", "1.5", "-1"):
            with self.subTest(ts_ms=bad_ts):
                headers = dict(self.headers, ts_ms=bad_ts)
                with self.assertRaises(HeaderError):
                    verify_envelope(self.secret, DEVICE_TOPIC, PAYLOAD, headers)

    def test_signature_binds_topic_correlation_timestamp_and_key(self) -> None:
        tampered = {
            "other topic scope": (OTHER_DEVICE_TOPIC, self.secret, self.headers),
            "other device key": (DEVICE_TOPIC, self.other_secret, self.headers),
            "other correlation_id": (
                DEVICE_TOPIC, self.secret, dict(self.headers, correlation_id="cid-other")
            ),
            "other ts_ms": (
                DEVICE_TOPIC, self.secret, dict(self.headers, ts_ms=str(self.ts_ms + 1))
            ),
        }
        for label, (topic, secret, headers) in tampered.items():
            with self.subTest(case=label):
                with self.assertRaises(SignatureError):
                    verify_envelope(secret, topic, PAYLOAD, headers)

    def test_valid_envelope_keeps_scope_and_correlation(self) -> None:
        cid, ts_ms, headers = verify_envelope(self.secret, DEVICE_TOPIC, PAYLOAD, self.headers)
        self.assertEqual((cid, ts_ms), ("cid-scope-1", self.ts_ms))
        self.assertEqual(headers["correlation_id"], "cid-scope-1")

    def test_forged_message_does_not_consume_correlation_id(self) -> None:
        forged = dict(self.headers, signature=_flip_last_hex(self.headers["signature"]))
        with self.assertRaises(SignatureError):
            verify_envelope(self.secret, DEVICE_TOPIC, PAYLOAD, forged, replay_guard=self.guard)
        self.assertEqual(len(self.guard), 0)
        verify_envelope(self.secret, DEVICE_TOPIC, PAYLOAD, self.headers, replay_guard=self.guard)
        self.assertEqual(len(self.guard), 1)

    def test_replay_rejection_does_not_grow_guard_state(self) -> None:
        verify_envelope(self.secret, DEVICE_TOPIC, PAYLOAD, self.headers, replay_guard=self.guard)
        with self.assertRaises(ReplayError):
            verify_envelope(
                self.secret, DEVICE_TOPIC, PAYLOAD, self.headers, replay_guard=self.guard
            )
        self.assertEqual(len(self.guard), 1)

    def test_same_correlation_id_on_other_scope_is_still_duplicate(self) -> None:
        # Guard theo correlation_id toàn cục: ID đã dùng cho thiết bị 001 bị chặn
        # kể cả khi bản tin hợp lệ thứ hai ký đúng cho thiết bị 002.
        verify_envelope(self.secret, DEVICE_TOPIC, PAYLOAD, self.headers, replay_guard=self.guard)
        second_headers, _, _ = build_headers(
            self.other_secret,
            OTHER_DEVICE_TOPIC,
            PAYLOAD,
            correlation_id="cid-scope-1",
            ts_ms=self.now,
        )
        with self.assertRaises(ReplayError):
            verify_envelope(
                self.other_secret,
                OTHER_DEVICE_TOPIC,
                PAYLOAD,
                second_headers,
                replay_guard=self.guard,
            )

    def test_enforce_timestamp_false_bypasses_guard_for_stale_message(self) -> None:
        stale_ts = self.now - 10_000
        stale, _, _ = build_headers(
            self.secret, DEVICE_TOPIC, PAYLOAD, correlation_id="cid-lwt", ts_ms=stale_ts
        )
        with self.assertRaises(ReplayError):
            verify_envelope(self.secret, DEVICE_TOPIC, PAYLOAD, stale, replay_guard=self.guard)
        for _ in range(2):
            cid, ts_ms, _ = verify_envelope(
                self.secret,
                DEVICE_TOPIC,
                PAYLOAD,
                stale,
                replay_guard=self.guard,
                enforce_timestamp=False,
            )
            self.assertEqual((cid, ts_ms), ("cid-lwt", stale_ts))
        self.assertEqual(len(self.guard), 0)

    def test_payload_text_and_bytes_verify_equivalently(self) -> None:
        text = '{"ten":"Đèn LED","requested_value":50}'
        headers, _, _ = build_headers(self.secret, DEVICE_TOPIC, text, ts_ms=self.now)
        verify_envelope(self.secret, DEVICE_TOPIC, text.encode("utf-8"), headers)
        verify_envelope(self.secret, DEVICE_TOPIC, text, headers)

    @unittest.skipUnless(
        os.environ.get("PCCOM_RUN_CHARACTERIZATION") == "1",
        "Non-normative characterization; enable PCCOM_RUN_CHARACTERIZATION=1",
    )
    def test_characterize_uppercase_signature_property_is_accepted(self) -> None:
        headers = dict(self.headers, signature=self.headers["signature"].upper())
        cid, _, _ = verify_envelope(self.secret, DEVICE_TOPIC, PAYLOAD, headers)
        self.assertEqual(cid, "cid-scope-1")


class ReplayGuardBoundaryRegressionTests(unittest.TestCase):
    """O-SIG: ranh giới cửa sổ và vòng đời bộ nhớ của ReplayGuard."""

    def setUp(self) -> None:
        self.now = NOW
        self.guard = ReplayGuard(window_ms=1000, future_skew_ms=100, clock_ms=lambda: self.now)

    def test_constructor_rejects_invalid_windows(self) -> None:
        with self.assertRaises(ValueError):
            ReplayGuard(window_ms=0)
        with self.assertRaises(ValueError):
            ReplayGuard(window_ms=-1)
        with self.assertRaises(ValueError):
            ReplayGuard(window_ms=1000, future_skew_ms=-1)
        ReplayGuard(window_ms=1, future_skew_ms=0)  # biên hợp lệ, không ném lỗi

    def test_window_and_skew_boundaries_are_inclusive(self) -> None:
        self.guard.check_and_record("cid-oldest", self.now - 1000)
        self.guard.check_and_record("cid-newest", self.now + 100)
        self.assertEqual(len(self.guard), 2)
        with self.assertRaises(ReplayError):
            self.guard.check_and_record("cid-too-old", self.now - 1001)
        with self.assertRaises(ReplayError):
            self.guard.check_and_record("cid-too-new", self.now + 101)

    def test_missing_correlation_id_is_rejected(self) -> None:
        for cid in ("", None):
            with self.subTest(correlation_id=cid):
                with self.assertRaises(ReplayError):
                    self.guard.check_and_record(cid, self.now)  # type: ignore[arg-type]

    def test_rejected_timestamp_is_not_recorded(self) -> None:
        with self.assertRaises(ReplayError):
            self.guard.check_and_record("cid-1", self.now - 5000)
        self.assertEqual(len(self.guard), 0)
        self.guard.check_and_record("cid-1", self.now)
        self.assertEqual(len(self.guard), 1)

    def test_duplicate_does_not_grow_memory_and_id_expires_after_window(self) -> None:
        self.guard.check_and_record("cid-1", self.now)
        with self.assertRaises(ReplayError):
            self.guard.check_and_record("cid-1", self.now)
        self.assertEqual(len(self.guard), 1)

        self.now += 1000  # đúng biên: mục có ts == now - window chưa bị dọn
        with self.assertRaises(ReplayError):
            self.guard.check_and_record("cid-1", self.now)

        self.now += 1  # vượt biên một mili-giây: mục bị dọn, ID dùng lại được
        self.guard.check_and_record("cid-1", self.now)
        self.assertEqual(len(self.guard), 1)


class NorthboundEnvelopeRegressionTests(unittest.TestCase):
    """O-NBP: build_envelope / parse_envelope / target helpers."""

    def _envelope(self, **overrides):
        base = dict(
            tenant_id="t1",
            site_id="s01",
            gateway_id="gw-001",
            source_site_id="SITE_01",
            device_type="light",
            device_id="LGT_NODE_001",
            category="telemetry",
            data={"asset_id": "LGT_NODE_001", "source_time": 100},
        )
        base.update(overrides)
        return build_envelope(**base)

    def test_parse_rejects_non_json_and_wrong_shapes(self) -> None:
        for payload in ("not json", "[]", "123", "null", '"text"', b"\xff\xfe", 123, None):
            with self.subTest(payload=payload):
                with self.assertRaises(NorthboundPayloadError):
                    parse_envelope(payload)  # type: ignore[arg-type]

    def test_parse_accepts_text_and_bytes_equivalently(self) -> None:
        encoded = encode_envelope(self._envelope(data={"ten": "Đèn LED"}))
        self.assertEqual(parse_envelope(encoded), parse_envelope(encoded.encode("utf-8")))

    def test_parse_reports_each_missing_required_field(self) -> None:
        full = self._envelope()
        for field in (
            "tenant_id",
            "site_id",
            "gateway_id",
            "device_type",
            "device_id",
            "category",
            "data",
        ):
            with self.subTest(field=field):
                partial = {key: value for key, value in full.items() if key != field}
                with self.assertRaisesRegex(NorthboundPayloadError, field):
                    parse_envelope(json.dumps(partial))

    def test_parse_rejects_invalid_identity_values(self) -> None:
        full = self._envelope()
        invalid = {
            "tenant_id": "t/1",
            "site_id": "s+01",
            "gateway_id": "gw#1",
            "device_type": "camera",
            "device_id": "LGT NODE",
            "category": "bogus",
        }
        for field, value in invalid.items():
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    parse_envelope(json.dumps(dict(full, **{field: value})))

    @unittest.skipUnless(
        os.environ.get("PCCOM_RUN_CHARACTERIZATION") == "1",
        "Non-normative characterization; enable PCCOM_RUN_CHARACTERIZATION=1",
    )
    def test_characterize_non_string_identity_is_coerced_not_rejected(self) -> None:
        # parse_envelope kiểm str(value) nên tenant_id số nguyên vẫn qua. Chưa có
        # oracle yêu cầu identity phải là chuỗi, nên chỉ ghi lại hiện trạng.
        parsed = parse_envelope(json.dumps(dict(self._envelope(), tenant_id=1)))
        self.assertEqual(parsed["tenant_id"], 1)

    def test_build_rejects_invalid_inputs(self) -> None:
        for field, value in (
            ("tenant_id", "t/1"),
            ("site_id", ""),
            ("gateway_id", "gw 1"),
            ("source_site_id", "SITE#1"),
            ("device_type", "camera"),
            ("device_id", "a/b"),
            ("category", "bogus"),
        ):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    self._envelope(**{field: value})
        for bad_data in ({1, 2}, object(), b"bytes"):
            with self.subTest(data=type(bad_data).__name__):
                with self.assertRaises(NorthboundPayloadError):
                    self._envelope(data=bad_data)

    def test_build_preserves_scope_and_generates_unique_message_ids(self) -> None:
        first = self._envelope(category="cmd")
        second = self._envelope(category="cmd")
        self.assertEqual(
            {key: first[key] for key in (
                "tenant_id", "site_id", "gateway_id", "source_site_id",
                "device_type", "device_id", "category", "quality", "schema_version",
            )},
            {
                "tenant_id": "t1", "site_id": "s01", "gateway_id": "gw-001",
                "source_site_id": "SITE_01", "device_type": "light",
                "device_id": "LGT_NODE_001", "category": "cmd", "quality": "GOOD",
                "schema_version": "1.0.0",
            },
        )
        self.assertNotEqual(first["message_id"], second["message_id"])
        self.assertEqual(uuid.UUID(first["message_id"]).version, 4)

    def test_build_source_time_precedence_and_received_time(self) -> None:
        with patch("iot_protocol.northbound_payload.time.time", return_value=1_700_000_000.9):
            explicit = self._envelope(source_time=7, data={"source_time": 100})
            from_data = self._envelope(data={"source_time": 100, "device_time": 200})
            from_device_time = self._envelope(data={"device_time": 200})
            defaulted = self._envelope(data={"other": 1})
            non_dict = self._envelope(data=[1, 2])
        self.assertEqual(explicit["source_time"], 7)
        self.assertEqual(from_data["source_time"], 100)
        self.assertEqual(from_device_time["source_time"], 200)
        self.assertEqual(defaulted["source_time"], 1_700_000_000)
        self.assertEqual(non_dict["source_time"], 1_700_000_000)
        self.assertEqual(defaulted["received_time"], 1_700_000_000)

    def test_build_asset_id_resolution_and_extra_overlay(self) -> None:
        self.assertEqual(self._envelope(data={"asset_id": "A1"})["asset_id"], "A1")
        self.assertEqual(self._envelope(data={"device_id": "D1"})["asset_id"], "D1")
        self.assertEqual(self._envelope(data={"x": 1})["asset_id"], "LGT_NODE_001")
        self.assertEqual(self._envelope(data=[1])["asset_id"], "LGT_NODE_001")
        with_extra = self._envelope(extra={"command_id": "cmd-1", "action": "DIM"})
        self.assertEqual((with_extra["command_id"], with_extra["action"]), ("cmd-1", "DIM"))

    def test_command_target_rejects_incomplete_targets(self) -> None:
        incomplete = {
            "missing device_id": {"source_site_id": "SITE_01", "device_type": "light"},
            "missing source_site_id": {"device_type": "light", "device_id": "LGT_NODE_001"},
            "missing device_type": {"source_site_id": "SITE_01", "device_id": "LGT_NODE_001"},
            "empty device_id": {
                "source_site_id": "SITE_01", "device_type": "light", "device_id": "",
            },
            "nested without device_type": {
                "source_site_id": "SITE_01", "target": {"device_id": "LGT_NODE_001"},
            },
            "nested without id": {
                "source_site_id": "SITE_01", "target": {"device_type": "light"},
            },
        }
        for label, envelope in incomplete.items():
            with self.subTest(case=label):
                with self.assertRaises(NorthboundPayloadError):
                    command_target(envelope)

    def test_command_target_identifier_precedence(self) -> None:
        nested = {
            "source_site_id": "SITE_01",
            "target": {"device_id": "DEV", "asset_id": "AST", "device_type": "light"},
        }
        flat = {
            "source_site_id": "SITE_01", "device_type": "light",
            "device_id": "DEV", "asset_id": "AST",
        }
        self.assertEqual(command_target(nested), ("SITE_01", "light", "DEV"))
        self.assertEqual(command_target(flat), ("SITE_01", "light", "DEV"))

    def test_envelope_device_key_requires_source_site(self) -> None:
        self.assertEqual(
            envelope_device_key(self._envelope()),
            ("SITE_01", "light", "LGT_NODE_001"),
        )
        for envelope in (
            {"device_type": "light", "device_id": "LGT_NODE_001"},
            {"source_site_id": "", "device_type": "light", "device_id": "LGT_NODE_001"},
        ):
            with self.subTest(envelope=envelope):
                with self.assertRaises(NorthboundPayloadError):
                    envelope_device_key(envelope)


class GatewayKeyRegressionTests(unittest.TestCase):
    """O-NBP: phạm vi khóa gateway."""

    def test_empty_master_secret_is_rejected(self) -> None:
        with self.assertRaises(NorthboundPayloadError):
            derive_gateway_key("", "t1", "s01", "gw-001")

    def test_key_changes_with_each_scope_component(self) -> None:
        base = derive_gateway_key("master", "t1", "s01", "gw-001")
        self.assertEqual(len(base), 32)
        for label, other in (
            ("tenant", derive_gateway_key("master", "t2", "s01", "gw-001")),
            ("site", derive_gateway_key("master", "t1", "s02", "gw-001")),
            ("gateway", derive_gateway_key("master", "t1", "s01", "gw-002")),
            ("master", derive_gateway_key("master-2", "t1", "s01", "gw-001")),
        ):
            with self.subTest(component=label):
                self.assertNotEqual(base, other)

    @unittest.skipUnless(
        os.environ.get("PCCOM_RUN_CHARACTERIZATION") == "1",
        "Non-normative characterization; enable PCCOM_RUN_CHARACTERIZATION=1",
    )
    def test_characterize_key_derivation_does_not_validate_segments(self) -> None:
        # Hai hàm dẫn xuất khóa không tự kiểm segment: site_id chứa '/' làm khóa
        # thiết bị trùng khóa gateway. Đầu vào đó bị validate_segment chặn ở lớp
        # topic/config; test ghi lại cả hai vế để làm rõ phạm vi rủi ro.
        colliding_site = "t1/s01"
        self.assertEqual(
            derive_device_key("master", colliding_site, "gateway", "gw-001"),
            derive_gateway_key("master", "t1", "s01", "gw-001"),
        )
        with self.assertRaises(TopicError):
            validate_segment(colliding_site, "site_id")


class NorthboundAckChainRegressionTests(unittest.TestCase):
    """O-NBP + O-HDR: chuỗi helper envelope -> ký -> xác thực (không có broker)."""

    def setUp(self) -> None:
        self.now = NOW
        self.key = derive_gateway_key("master-secret-for-test", "t1", "s01", "gw-001")
        self.topic = northbound_topic("t1", "s01", "gw-001", "ack")
        self.payload = encode_envelope(
            build_envelope(
                tenant_id="t1",
                site_id="s01",
                gateway_id="gw-001",
                source_site_id="SITE_01",
                device_type="light",
                device_id="LGT_NODE_001",
                category="ack",
                data={"status": normalize_ack_status("EXECUTED")},
                extra={"command_id": "cmd-77"},
            )
        )
        self.headers, self.cid, _ = build_headers(
            self.key, self.topic, self.payload, correlation_id="cmd-77", ts_ms=self.now
        )

    def test_ack_roundtrip_keeps_correlation_and_status_vocabulary(self) -> None:
        cid, _, _ = verify_envelope(self.key, self.topic, self.payload, self.headers)
        parsed = parse_envelope(self.payload)
        self.assertEqual(cid, "cmd-77")
        self.assertEqual(parsed["command_id"], "cmd-77")
        self.assertEqual(parsed["data"]["status"], "executed")
        self.assertEqual(parsed["category"], "ack")

    def test_ack_is_rejected_for_other_gateway_key_or_other_category_topic(self) -> None:
        other_gateway_key = derive_gateway_key("master-secret-for-test", "t1", "s02", "gw-002")
        with self.assertRaises(SignatureError):
            verify_envelope(other_gateway_key, self.topic, self.payload, self.headers)
        with self.assertRaises(SignatureError):
            verify_envelope(
                self.key,
                northbound_topic("t1", "s01", "gw-001", "cmd"),
                self.payload,
                self.headers,
            )

    def test_duplicate_ack_delivery_is_rejected_by_replay_guard(self) -> None:
        guard = ReplayGuard(window_ms=1000, clock_ms=lambda: self.now)
        verify_envelope(self.key, self.topic, self.payload, self.headers, replay_guard=guard)
        with self.assertRaises(ReplayError):
            verify_envelope(self.key, self.topic, self.payload, self.headers, replay_guard=guard)

    def test_payload_modified_after_signing_is_rejected(self) -> None:
        tampered = self.payload.replace('"executed"', '"rejected"')
        self.assertNotEqual(tampered, self.payload)
        with self.assertRaises(SignatureError):
            verify_envelope(self.key, self.topic, tampered, self.headers)


class AckStatusVocabularyRegressionTests(unittest.TestCase):
    """O-NBP: normalize_ack_status."""

    def test_full_vocabulary_maps_case_insensitively(self) -> None:
        for raw, expected in ACK_STATUS_MAP.items():
            for variant in (raw, raw.lower(), raw.title(), f"  {raw}  "):
                with self.subTest(raw=variant):
                    self.assertEqual(normalize_ack_status(variant), expected)

    def test_missing_or_blank_status_is_unknown(self) -> None:
        for raw in (None, "", "   ", 0, False):
            with self.subTest(raw=raw):
                self.assertEqual(normalize_ack_status(raw), "unknown")

    @unittest.skipUnless(
        os.environ.get("PCCOM_RUN_CHARACTERIZATION") == "1",
        "Non-normative characterization; enable PCCOM_RUN_CHARACTERIZATION=1",
    )
    def test_characterize_out_of_vocabulary_status_passes_through_lowercased(self) -> None:
        # Giá trị ngoài từ vựng không bị ép về "unknown". Từ vựng cho phép của
        # Tech Lead chưa được xác nhận bằng nguồn nên chỉ ghi lại hiện trạng.
        self.assertEqual(normalize_ack_status("PENDING"), "pending")
        self.assertEqual(normalize_ack_status("Weird Value"), "weird value")


if __name__ == "__main__":
    unittest.main()
