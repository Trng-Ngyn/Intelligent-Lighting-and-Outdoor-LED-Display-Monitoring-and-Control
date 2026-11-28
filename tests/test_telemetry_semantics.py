"""AUTO-G1-007 (Feasible Runtime Slice) - Telemetry Provenance & Semantics tests.

Phạm vi: kiểm thử các đường thực thi telemetry HIỆN CÓ trong ``src/``:
- ``edge_gateway_bridge.bridge.GatewayLink`` (xác thực & chuyển tiếp telemetry từ
  southbound lên northbound envelope).
- ``edge_simulator.simulator_device.SimulatorDevice.publish_telemetry`` (phát
  telemetry thiết bị với clock cố định và trạng thái relay ON/OFF).
- ``backend.mock_cloud_service.MockCloudService`` (tiếp nhận & ghi nhận telemetry
  southbound/northbound).

Không trùng lặp với unit test của ``build_envelope`` trong Batch 1 hay JSON Schema
tests trong ``AUTO-G1-002`` / ``AUTO-G1-004``. Không tự đặt ngưỡng freshness, ánh xạ
quality hay canonical adapter chưa được phê duyệt.

Test Oracle:
- O-BRIDGE-TEL: ``contracts/README.md`` (mục telemetry) và ``bridge.py:352-488`` —
  bảo toàn ``source_time`` của thiết bị tách biệt khỏi ``received_time`` tại gateway,
  giữ nguyên định danh thiết bị và không ép giá trị ``None`` / thiếu về ``0``.
- O-SIM-TEL: ``simulator_device.py:205-281`` — khi ``relay_state=False`` thì công suất
  và dòng điện bằng ``0.0`` thực sự (phân biệt với ``None``/thiếu), ``source_time`` lấy
  theo clock và ``sequence`` tăng đơn điệu.
- O-CLOUD-TEL: ``mock_cloud_service.py:571-603, 714-746`` — trường metric vắng mặt
  hoặc ``null`` được đọc là ``None``, không tự diễn giải thành ``0``.
- O-CHAR (CHỈ GHI NHẬN HIỆN TRẠNG - KHÔNG PHẢI ACCEPTANCE): lớp characterization
  (mặc định skip; bật opt-in bằng ``PCCOM_RUN_CHARACTERIZATION=1``) ghi lại việc
  bridge ghi đè top-level ``quality`` về ``"GOOD"``, fallback ``source_time`` không
  gắn cờ ``uncertain``, chưa có bộ lọc freshness cho ``source_time`` cũ, simulator
  gán cứng ``quality="GOOD"`` không có cờ ``simulated``, và backend chưa lưu/cập
  nhật state từ telemetry.

Trace: LGT 01/05, DAT 01/02; TS-G1-LGT-01, TS-G1-LGT-05; TC-G1-LGT-01-002,
TC-G1-LGT-05-001. Trạng thái tổng thể AUTO-G1-007: PARTIALLY READY (canonical
normalization & freshness threshold policy vẫn BLOCKED / PENDING CONFIRMATION).
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from backend import core_api
from backend.mock_cloud_service import MockCloudService
from edge_gateway_bridge.bridge import GatewayLink
from edge_simulator.config import DeviceSpec, load_config
from edge_simulator.simulator_device import SimulatorDevice
from iot_protocol.headers import build_headers, verify_envelope
from iot_protocol.mqtt5 import CONTENT_TYPE_JSON, make_publish_properties
from iot_protocol.northbound_payload import parse_envelope
from iot_protocol.northbound_topics import northbound_topic, parse_northbound_topic
from iot_protocol.signing import ReplayGuard, derive_device_key
from iot_protocol.topics import telemetry_topic

REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_CONFIG = REPO_ROOT / "tests" / "fixtures" / "simulator.test.json"
SITE = "SITE_TEST_01"
DEVICE_ID = "LGT_NODE_001"

SOURCE_TIME_SEC = 1_700_000_010
GATEWAY_RX_SEC = 1_700_000_025.4
HEADER_TS_MS = 1_700_000_025_000


class FakeMqttClient:
    """Test double cho Mqtt5Client ở cả Simulator, Bridge và MockCloud."""

    def __init__(self, broker=None, client_id: str = "", logger=None) -> None:
        self.broker = broker
        self.client_id = client_id
        self.logger = logger
        self.is_connected = True
        self.callbacks: dict[str, Any] = {}
        self.published: list[dict[str, Any]] = []

    def set_callbacks(self, **kwargs: Any) -> None:
        self.callbacks.update(kwargs)

    def publish(
        self,
        topic: str,
        payload: str | bytes,
        qos: int = 0,
        retain: bool = False,
        properties: Any = None,
        wait_for_ack: bool = True,
    ) -> bool:
        self.published.append(
            dict(
                topic=topic,
                payload=payload,
                qos=qos,
                retain=retain,
                properties=properties,
                wait_for_ack=wait_for_ack,
            )
        )
        return True

    def stop(self) -> None:
        self.is_connected = False


@dataclass
class FakeInboundMessage:
    """Gói tin MQTT 5 tổng hợp truyền trực tiếp vào _handle_message."""

    topic: str
    payload: bytes
    properties: Any


class TelemetryRuntimeHarness(unittest.TestCase):
    """Môi trường cô lập với fixture config, clock điều khiển được và cấm mạng."""

    def setUp(self) -> None:
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith("SIM_")}
        with patch.dict(os.environ, clean_env, clear=True):
            self.config = load_config(str(TEST_CONFIG))
        self.spec: DeviceSpec = self.config.device_index()[(SITE, "light", DEVICE_ID)]
        self.device_secret = derive_device_key(
            self.config.security.signing_secret,
            self.spec.site_id,
            self.spec.device_type,
            self.spec.device_id,
        )
        self.logger = logging.getLogger("test.telemetry_semantics")
        self.logger.handlers.clear()
        self.logger.addHandler(logging.NullHandler())
        self.logger.propagate = False

        self._patch(
            patch("socket.socket.connect", side_effect=AssertionError("network access"))
        )
        self._patch(patch("edge_gateway_bridge.bridge.Mqtt5Client", FakeMqttClient))
        self._patch(patch("edge_simulator.simulator_device.Mqtt5Client", FakeMqttClient))
        self._patch(patch("backend.mock_cloud_service.Mqtt5Client", FakeMqttClient))

    def _patch(self, patcher):
        started = patcher.start()
        self.addCleanup(patcher.stop)
        return started

    def make_gateway_link(self, guard_now_ms: int = HEADER_TS_MS) -> GatewayLink:
        link = GatewayLink(self.config, SITE, "gw-001", self.logger)
        for key in list(link.device_guards):
            link.device_guards[key] = ReplayGuard(
                window_ms=self.config.settings.replay_window_ms,
                clock_ms=lambda: guard_now_ms,
            )
        return link

    def make_southbound_telemetry_msg(
        self,
        payload_raw: dict[str, Any] | bytes,
        *,
        ts_ms: int = HEADER_TS_MS,
        correlation_id: str = "cid-tel-001",
    ) -> FakeInboundMessage:
        topic = telemetry_topic(SITE, "light", DEVICE_ID)
        if isinstance(payload_raw, bytes):
            payload_bytes = payload_raw
        else:
            payload_bytes = json.dumps(
                payload_raw, ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8")
        headers, cid, _ = build_headers(
            self.device_secret,
            topic,
            payload_bytes,
            correlation_id=correlation_id,
            ts_ms=ts_ms,
        )
        props = make_publish_properties(
            headers,
            content_type=CONTENT_TYPE_JSON,
            correlation_data=cid.encode("utf-8"),
        )
        return FakeInboundMessage(topic=topic, payload=payload_bytes, properties=props)


class TelemetryForwardingAndProvenanceVerificationTests(TelemetryRuntimeHarness):
    """O-BRIDGE-TEL / O-SIM-TEL / O-CLOUD-TEL: kiểm chứng hành vi đã có Oracle."""

    def test_gateway_bridge_preserves_device_source_time_distinct_from_received_time(
        self,
    ) -> None:
        link = self.make_gateway_link(guard_now_ms=HEADER_TS_MS)
        southbound_payload = {
            "schema_version": "1.0.0",
            "message_id": "MSG_SYN_001",
            "asset_id": DEVICE_ID,
            "sequence": 12,
            "source_time": SOURCE_TIME_SEC,
            "metrics": {
                "power_w": 48.5,
                "energy_wh": 120.25,
                "voltage_v": 220.2,
                "current_a": 0.22,
                "power_factor": 0.95,
                "temperature_c": 37.0,
                "ambient_lux": 18.5,
            },
            "brightness_pct": 50,
            "relay_state": True,
            "quality": "GOOD",
        }
        message = self.make_southbound_telemetry_msg(southbound_payload)

        with patch(
            "iot_protocol.northbound_payload.time.time",
            return_value=GATEWAY_RX_SEC,
        ):
            link._handle_message(message)

        self.assertEqual(len(link.client.published), 1)
        sent = link.client.published[0]
        expected_topic = northbound_topic("t1", "s01", "gw-001", "telemetry")
        self.assertEqual(sent["topic"], expected_topic)
        self.assertEqual((sent["qos"], sent["retain"]), (1, False))

        verified_cid, verified_ts_ms, _ = verify_envelope(
            link.gateway_secret,
            sent["topic"],
            sent["payload"],
            sent["properties"].UserProperty,
            enforce_timestamp=False,
        )
        self.assertTrue(verified_cid)
        self.assertEqual(verified_ts_ms, int(GATEWAY_RX_SEC * 1000))

        envelope = parse_envelope(sent["payload"])
        self.assertEqual(envelope["source_time"], SOURCE_TIME_SEC)
        self.assertEqual(envelope["received_time"], int(GATEWAY_RX_SEC))
        self.assertGreater(envelope["received_time"], envelope["source_time"])
        self.assertEqual(envelope["source_site_id"], SITE)
        self.assertEqual(envelope["device_type"], "light")
        self.assertEqual(envelope["device_id"], DEVICE_ID)
        self.assertEqual(envelope["asset_id"], DEVICE_ID)
        self.assertEqual(envelope["data"]["sequence"], 12)
        self.assertEqual(envelope["data"]["source_time"], SOURCE_TIME_SEC)

    def test_gateway_bridge_preserves_null_and_missing_metrics_without_zero_coercion(
        self,
    ) -> None:
        scenarios = {
            "null_unavailable_metrics": (
                {"power_w": None, "ambient_lux": None, "voltage_v": 220.1},
                lambda m: (
                    m["power_w"] is None
                    and m["ambient_lux"] is None
                    and m["voltage_v"] == 220.1
                ),
            ),
            "omitted_metrics": (
                {"voltage_v": 220.1},
                lambda m: (
                    "power_w" not in m
                    and m.get("power_w") is None
                    and "temperature_c" not in m
                    and m["voltage_v"] == 220.1
                ),
            ),
            "explicit_measured_zero": (
                {"power_w": 0.0, "current_a": 0.0, "voltage_v": 220.0},
                lambda m: (
                    m["power_w"] == 0.0
                    and m["power_w"] is not None
                    and m["current_a"] == 0.0
                    and m["current_a"] is not None
                ),
            ),
        }
        for idx, (label, (metrics, predicate)) in enumerate(scenarios.items(), 1):
            with self.subTest(case=label):
                link = self.make_gateway_link(guard_now_ms=HEADER_TS_MS)
                payload = {
                    "schema_version": "1.0.0",
                    "message_id": f"MSG_NULL_{idx}",
                    "asset_id": DEVICE_ID,
                    "sequence": idx,
                    "source_time": SOURCE_TIME_SEC,
                    "metrics": metrics,
                    "quality": "GOOD",
                }
                msg = self.make_southbound_telemetry_msg(
                    payload, correlation_id=f"cid-null-{idx}"
                )
                with patch(
                    "iot_protocol.northbound_payload.time.time",
                    return_value=GATEWAY_RX_SEC,
                ):
                    link._handle_message(msg)

                self.assertEqual(len(link.client.published), 1)
                envelope = parse_envelope(link.client.published[0]["payload"])
                forwarded_metrics = envelope["data"]["metrics"]
                self.assertTrue(predicate(forwarded_metrics), forwarded_metrics)

    def test_simulator_relay_off_emits_true_zero_power_with_deterministic_source_time(
        self,
    ) -> None:
        device = SimulatorDevice(self.spec, self.config, self.logger)
        initial_wh = device.cumulative_wh

        device.relay_state = False
        device.brightness = 0
        with (
            patch(
                "edge_simulator.simulator_device.time.time",
                return_value=1_700_000_500.9,
            ),
            patch(
                "edge_simulator.simulator_device.now_ms",
                return_value=1_700_000_500_900,
            ),
            patch(
                "iot_protocol.headers.now_ms",
                return_value=1_700_000_500_900,
            ),
        ):
            device.publish_telemetry()

        self.assertEqual(len(device.client.published), 1)
        off_msg = device.client.published[0]
        off_payload = json.loads(off_msg["payload"])
        self.assertEqual(off_payload["source_time"], 1_700_000_500)
        self.assertEqual(off_payload["sequence"], 1)
        self.assertEqual(off_payload["relay_state"], False)
        self.assertEqual(off_payload["metrics"]["power_w"], 0.0)
        self.assertEqual(off_payload["metrics"]["current_a"], 0.0)
        self.assertEqual(off_payload["metrics"]["energy_wh"], round(initial_wh, 2))
        verify_envelope(
            device.secret,
            off_msg["topic"],
            off_msg["payload"],
            off_msg["properties"].UserProperty,
            enforce_timestamp=False,
        )

        device.relay_state = True
        device.brightness = 60
        with patch("edge_simulator.simulator_device.time.time", return_value=1_700_000_515.2):
            device.publish_telemetry()

        on_payload = json.loads(device.client.published[1]["payload"])
        self.assertEqual(on_payload["source_time"], 1_700_000_515)
        self.assertEqual(on_payload["sequence"], 2)
        self.assertGreater(on_payload["metrics"]["power_w"], 0.0)
        self.assertGreater(on_payload["metrics"]["current_a"], 0.0)

    def test_mock_cloud_logs_missing_and_null_metrics_as_none_not_zero(self) -> None:
        cloud_logger = logging.getLogger("test.mock_cloud.telemetry")
        cloud = MockCloudService(self.config, cloud_logger, northbound=True)
        sparse_payload = {
            "asset_id": DEVICE_ID,
            "sequence": 9,
            "source_time": SOURCE_TIME_SEC,
            "metrics": {"power_w": None, "voltage_v": 220.5},
        }
        raw_bytes = json.dumps(sparse_payload).encode("utf-8")

        with self.assertLogs(cloud_logger, level="INFO") as sb_logs:
            cloud._handle_telemetry(
                telemetry_topic(SITE, "light", DEVICE_ID),
                raw_bytes,
                "cid-sb-1",
                HEADER_TS_MS,
            )
        self.assertIn("power_w=None", sb_logs.output[0])
        self.assertIn("temp_c=None", sb_logs.output[0])
        self.assertIn("lux=None", sb_logs.output[0])
        self.assertIn("voltage_v=220.5", sb_logs.output[0])

        nb_topic = northbound_topic("t1", "s01", "gw-001", "telemetry")
        parsed_nb = parse_northbound_topic(nb_topic)
        state = cloud.devices[self.spec.key]
        with self.assertLogs(cloud_logger, level="INFO") as nb_logs:
            cloud._handle_northbound_telemetry(
                state,
                parsed_nb,
                {"data": sparse_payload},
                nb_topic,
                "cid-nb-1",
                HEADER_TS_MS,
            )
        self.assertIn("power_w=None", nb_logs.output[0])
        self.assertIn("temp_c=None", nb_logs.output[0])
        self.assertIn("lux=None", nb_logs.output[0])

    def test_gateway_bridge_drops_non_object_or_invalid_json_telemetry(self) -> None:
        for idx, bad_bytes in enumerate((b"not-valid-json", b"[1,2,3]", b'"scalar"'), 1):
            with self.subTest(payload=bad_bytes):
                link = self.make_gateway_link(guard_now_ms=HEADER_TS_MS)
                msg = self.make_southbound_telemetry_msg(
                    bad_bytes, correlation_id=f"cid-bad-{idx}"
                )
                link._handle_message(msg)
                self.assertEqual(link.client.published, [])


@unittest.skipUnless(
    os.environ.get("PCCOM_RUN_CHARACTERIZATION") == "1",
    "Non-normative characterization; enable PCCOM_RUN_CHARACTERIZATION=1",
)
class TelemetryProvenanceAndFreshnessCharacterizationTests(TelemetryRuntimeHarness):
    """O-CHAR: ghi nhận khoảng trống provenance & freshness hiện tại (non-acceptance)."""

    def test_characterize_bridge_overwrites_top_level_quality_to_good(self) -> None:
        # PD-B2-04: southbound truyền quality="ESTIMATED" hoặc "DEGRADED" (hợp lệ theo
        # schemas.json), nhưng _forward_southbound không truyền quality vào build_envelope
        # nên envelope["quality"] bị đặt mặc định thành "GOOD".
        for idx, sb_quality in enumerate(("ESTIMATED", "DEGRADED"), 1):
            with self.subTest(southbound_quality=sb_quality):
                link = self.make_gateway_link(guard_now_ms=HEADER_TS_MS)
                payload = {
                    "schema_version": "1.0.0",
                    "message_id": f"MSG_Q_{idx}",
                    "asset_id": DEVICE_ID,
                    "sequence": idx,
                    "source_time": SOURCE_TIME_SEC,
                    "metrics": {"power_w": 45.0},
                    "quality": sb_quality,
                }
                msg = self.make_southbound_telemetry_msg(
                    payload, correlation_id=f"cid-q-{idx}"
                )
                link._handle_message(msg)
                envelope = parse_envelope(link.client.published[0]["payload"])
                self.assertEqual(envelope["data"]["quality"], sb_quality)
                self.assertEqual(envelope["quality"], "GOOD")

    def test_characterize_bridge_missing_source_time_falls_back_to_received_time_unmarked(
        self,
    ) -> None:
        # PD-B2-05: thiếu source_time ở southbound được gán bằng received_time mà không
        # hạ bậc quality hay gắn cờ clock_quality="uncertain".
        link = self.make_gateway_link(guard_now_ms=HEADER_TS_MS)
        payload = {
            "schema_version": "1.0.0",
            "message_id": "MSG_NO_SRC_TIME",
            "asset_id": DEVICE_ID,
            "sequence": 1,
            "metrics": {"power_w": 40.0},
            "quality": "GOOD",
        }
        msg = self.make_southbound_telemetry_msg(payload, correlation_id="cid-nosrc")
        with patch("iot_protocol.northbound_payload.time.time", return_value=GATEWAY_RX_SEC):
            link._handle_message(msg)

        envelope = parse_envelope(link.client.published[0]["payload"])
        self.assertEqual(envelope["source_time"], int(GATEWAY_RX_SEC))
        self.assertEqual(envelope["received_time"], int(GATEWAY_RX_SEC))
        self.assertEqual(envelope["quality"], "GOOD")
        self.assertNotIn("clock_quality", envelope)

    def test_characterize_bridge_has_no_application_freshness_filter_for_stale_source_time(
        self,
    ) -> None:
        # PD-B2-06: khi MQTT 5 header ts_ms còn tươi, payload có source_time cũ 24 giờ
        # vẫn được bridge chuyển tiếp nguyên trạng với quality="GOOD" (chưa có policy
        # freshness ứng dụng được phê duyệt).
        fresh_header_ms = 1_700_086_400_000
        stale_source_sec = 1_700_000_000  # cũ hơn 86_400 giây (24 giờ)
        link = self.make_gateway_link(guard_now_ms=fresh_header_ms)
        payload = {
            "schema_version": "1.0.0",
            "message_id": "MSG_STALE_24H",
            "asset_id": DEVICE_ID,
            "sequence": 5,
            "source_time": stale_source_sec,
            "metrics": {"power_w": 50.0},
            "quality": "GOOD",
        }
        msg = self.make_southbound_telemetry_msg(
            payload, ts_ms=fresh_header_ms, correlation_id="cid-stale-24h"
        )
        with patch("iot_protocol.northbound_payload.time.time", return_value=1_700_086_400.0):
            link._handle_message(msg)

        self.assertEqual(len(link.client.published), 1)
        envelope = parse_envelope(link.client.published[0]["payload"])
        self.assertEqual(envelope["source_time"], stale_source_sec)
        self.assertEqual(envelope["received_time"], 1_700_086_400)
        self.assertEqual(envelope["quality"], "GOOD")

    def test_characterize_simulator_emits_good_quality_without_simulated_provenance(
        self,
    ) -> None:
        # PD-B2-07: dữ liệu sinh ngẫu nhiên từ SimulatorDevice gán cứng quality="GOOD",
        # không có trường provenance / simulated để tách khỏi đo đạc vật lý.
        device = SimulatorDevice(self.spec, self.config, self.logger)
        device.publish_telemetry()
        emitted = json.loads(device.client.published[0]["payload"])
        self.assertEqual(emitted["quality"], "GOOD")
        self.assertNotIn("provenance", emitted)
        self.assertNotIn("simulated", emitted)

    def test_characterize_backend_services_do_not_persist_or_ingest_telemetry(self) -> None:
        # PD-B2-08: MockCloudService không cập nhật DeviceState khi nhận telemetry và
        # core_api không đăng ký bất kỳ hàm xử lý/subscribe telemetry nào.
        cloud = MockCloudService(self.config, self.logger, northbound=False)
        state = cloud.devices[self.spec.key]
        self.assertIsNone(state.last_status)
        cloud._handle_telemetry(
            telemetry_topic(SITE, "light", DEVICE_ID),
            json.dumps({"asset_id": DEVICE_ID, "sequence": 1, "metrics": {"power_w": 42.0}}).encode(
                "utf-8"
            ),
            "cid-persist-check",
            HEADER_TS_MS,
        )
        self.assertIsNone(state.last_status)
        self.assertFalse(hasattr(state, "last_telemetry"))
        self.assertFalse(hasattr(core_api, "handle_telemetry"))


if __name__ == "__main__":
    unittest.main()
