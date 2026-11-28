"""AUTO-G1-006 - Unknown target handling và độ chính xác command result (Core API).

Phạm vi: HTTP command handler ``backend.core_api.CoreApiHandler.do_POST`` và hàm
``send_dim_command``. Mọi kiểm tra chạy bằng handler harness (không socket) với test
double cho MQTT client, bộ dispatch giả và fixture tổng hợp
``tests/fixtures/simulator.test.json``. Không broker, không mạng, không thiết bị.

Test Oracle:
- O-API-FN (ĐÃ XÁC LẬP ở mức hàm): docstring của ``send_dim_command`` /
  ``_find_light_spec`` và các helper giao thức (headers.py, signing.py,
  northbound_payload.py): brightness phải thuộc [0, 100], không có thiết bị ``light``
  tương ứng thì không publish, lệnh publish phải ký đúng, mang đúng correlation_id,
  response topic và expiry.
- O-API-HTTP (CHƯA XÁC LẬP cho acceptance): backlog AUTO-G1-006 yêu cầu quyết định
  explicit "broadcast" hay "deny" khi target không xác định, và validation phải
  chạy trước side effect. Quyết định này chưa có (cần BE/TL, DEP-02/07).
  Vì vậy lớp ``DimHandlerCharacterizationTests`` CHỈ ghi lại hành vi quan sát được
  (mặc định skip; bật opt-in bằng ``PCCOM_RUN_CHARACTERIZATION=1``); các test đó
  KHÔNG khẳng định hành vi là đúng. Assertion acceptance (deny, không ghi state,
  không publish với target không hợp lệ) được ghi BLOCKED trong báo cáo và không
  được cài ở đây.

Isolated unit/handler test không thay thế integration test với broker hay phần cứng.
"""

from __future__ import annotations

import copy
import http.client
import io
import json
import logging
import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from backend import core_api
from edge_simulator.config import load_config
from iot_protocol.headers import verify_envelope
from iot_protocol.mqtt5 import COMMAND_MESSAGE_EXPIRY_SEC
from iot_protocol.northbound_payload import derive_gateway_key, parse_envelope
from iot_protocol.signing import SignatureError, derive_device_key
from iot_protocol.topics import command_dim_topic, command_result_topic

REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_CONFIG = REPO_ROOT / "tests" / "fixtures" / "simulator.test.json"
SITE = "SITE_TEST_01"
IN_CONFIG = ("LGT_NODE_001", "LGT_NODE_002")
NOT_IN_CONFIG = "LGT_NODE_999"
ROUTE = "/api/v1/controls/dim"


class FakeMqttClient:
    """Test double của Mqtt5Client: ghi lại publish, không có kết nối nào."""

    def __init__(self, result: bool = True) -> None:
        self.result = result
        self.published: list[dict] = []

    def publish(self, topic, payload, qos=0, retain=False, properties=None):
        self.published.append(
            dict(topic=topic, payload=payload, qos=qos, retain=retain, properties=properties)
        )
        return self.result

    def stop(self) -> None:
        return None


class FakeDispatch:
    """Thay thế send_dim_command ở mức handler: ghi lại lời gọi."""

    def __init__(self, failing=()) -> None:
        self.calls: list[tuple[str, int]] = []
        self.failing = set(failing)

    def __call__(self, asset_id: str, brightness: int):
        self.calls.append((asset_id, brightness))
        return None if asset_id in self.failing else f"cid-{asset_id}"


def _asset(asset_id: str) -> dict:
    return {
        "asset_id": asset_id,
        "site_id": SITE,
        "brightness": 50,
        "relay": True,
        "power_w": 48.5,
        "status": "ONLINE",
    }


class CoreApiHarness(unittest.TestCase):
    """Cô lập toàn bộ global state của core_api cho từng test."""

    def setUp(self) -> None:
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith("SIM_")}
        with patch.dict(os.environ, clean_env, clear=True):
            self.config = load_config(str(TEST_CONFIG))
        self.secret = self.config.security.signing_secret
        self.assets = {
            asset_id: _asset(asset_id) for asset_id in (*IN_CONFIG, NOT_IN_CONFIG)
        }
        self.client = FakeMqttClient()

        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)
        self._patch(patch.dict(core_api.ASSET_STATE, copy.deepcopy(self.assets), clear=True))
        self._patch(patch.object(core_api, "MQTT_CLIENT", self.client))
        self._patch(patch.object(core_api, "RUNTIME_CONFIG", self.config))
        self._patch(patch.object(core_api, "DEVICE_INDEX", self.config.device_index()))
        self._patch(patch.object(core_api, "NORTHBOUND_MODE", False))
        self._patch(patch.object(core_api.CoreApiHandler, "log_message"))
        # Chốt chặn cô lập: mọi nỗ lực mở kết nối mạng làm test thất bại.
        self._patch(
            patch("socket.socket.connect", side_effect=AssertionError("network access"))
        )

    def _patch(self, patcher):
        started = patcher.start()
        self.addCleanup(patcher.stop)
        return started

    @staticmethod
    def make_handler(path: str, body: bytes | None) -> core_api.CoreApiHandler:
        handler = core_api.CoreApiHandler.__new__(core_api.CoreApiHandler)
        headers = http.client.HTTPMessage()
        if body is not None:
            headers["Content-Length"] = str(len(body))
        handler.path = path
        handler.command = "POST"
        handler.request_version = "HTTP/1.1"
        handler.requestline = f"POST {path} HTTP/1.1"
        handler.client_address = ("127.0.0.1", 0)
        handler.headers = headers
        handler.rfile = io.BytesIO(body or b"")
        handler.wfile = io.BytesIO()
        return handler

    def post(self, body, path: str = ROUTE):
        """Chạy do_POST, trả về (status_code, json_body | None)."""
        raw = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        handler = self.make_handler(path, raw)
        handler.do_POST()
        return self.parse_response(handler)

    @staticmethod
    def parse_response(handler):
        head, _, payload = handler.wfile.getvalue().partition(b"\r\n\r\n")
        status = int(head.split(b" ", 2)[1])
        return status, (json.loads(payload) if payload else None)

    def state(self) -> dict:
        return copy.deepcopy(core_api.ASSET_STATE)


class SendDimCommandTests(CoreApiHarness):
    """O-API-FN: send_dim_command với fixture config và MQTT double."""

    def test_valid_command_is_signed_and_correlated(self) -> None:
        before = int(time.time())
        cid = core_api.send_dim_command("LGT_NODE_001", 30)
        after = int(time.time())

        self.assertIsNotNone(cid)
        self.assertEqual(len(self.client.published), 1)
        sent = self.client.published[0]
        topic = command_dim_topic(SITE, "light", "LGT_NODE_001")
        self.assertEqual(sent["topic"], topic)
        self.assertEqual((sent["qos"], sent["retain"]), (1, False))

        body = json.loads(sent["payload"])
        self.assertEqual(body["action"], "DIM")
        self.assertEqual(body["requested_value"], 30)
        self.assertEqual(body["command_id"], cid)
        self.assertTrue(
            before + COMMAND_MESSAGE_EXPIRY_SEC
            <= body["expires_at"]
            <= after + COMMAND_MESSAGE_EXPIRY_SEC
        )

        props = sent["properties"]
        self.assertEqual(dict(props.UserProperty)["correlation_id"], cid)
        self.assertEqual(props.CorrelationData, cid.encode("utf-8"))
        self.assertEqual(
            props.ResponseTopic, command_result_topic(SITE, "light", "LGT_NODE_001")
        )
        self.assertEqual(props.MessageExpiryInterval, COMMAND_MESSAGE_EXPIRY_SEC)
        self.assertEqual(props.ContentType, "application/json")

        device_key = derive_device_key(self.secret, SITE, "light", "LGT_NODE_001")
        verified_cid, _, _ = verify_envelope(
            device_key, topic, sent["payload"], props.UserProperty
        )
        self.assertEqual(verified_cid, cid)

    def test_command_is_scoped_to_target_device_key(self) -> None:
        core_api.send_dim_command("LGT_NODE_001", 30)
        sent = self.client.published[0]
        other_key = derive_device_key(self.secret, SITE, "light", "LGT_NODE_002")
        with self.assertRaises(SignatureError):
            verify_envelope(
                other_key, sent["topic"], sent["payload"], sent["properties"].UserProperty
            )

    def test_brightness_boundaries(self) -> None:
        for value in (0, 100):
            with self.subTest(accepted=value):
                self.assertIsNotNone(core_api.send_dim_command("LGT_NODE_001", value))
        accepted_publishes = len(self.client.published)
        self.assertEqual(accepted_publishes, 2)
        for value in (-1, 101):
            with self.subTest(rejected=value):
                with self.assertRaises(ValueError):
                    core_api.send_dim_command("LGT_NODE_001", value)
        self.assertEqual(len(self.client.published), accepted_publishes)

    def test_out_of_range_brightness_raises_even_without_client(self) -> None:
        with patch.object(core_api, "MQTT_CLIENT", None):
            with self.assertRaises(ValueError):
                core_api.send_dim_command("LGT_NODE_001", 101)

    def test_unknown_or_non_light_target_publishes_nothing(self) -> None:
        for asset_id in (NOT_IN_CONFIG, "NOPE", "DSP_LED_001", "ALL", ""):
            with self.subTest(asset_id=asset_id):
                self.assertIsNone(core_api.send_dim_command(asset_id, 40))
        self.assertEqual(self.client.published, [])

    def test_find_light_spec_only_matches_registered_light(self) -> None:
        self.assertEqual(core_api._find_light_spec("LGT_NODE_002").device_id, "LGT_NODE_002")
        for asset_id in ("DSP_LED_001", NOT_IN_CONFIG, "NOPE"):
            with self.subTest(asset_id=asset_id):
                self.assertIsNone(core_api._find_light_spec(asset_id))

    def test_publish_failure_returns_none(self) -> None:
        self.client.result = False
        self.assertIsNone(core_api.send_dim_command("LGT_NODE_001", 30))
        self.assertEqual(len(self.client.published), 1)

    def test_missing_client_returns_none_without_raising(self) -> None:
        with patch.object(core_api, "MQTT_CLIENT", None):
            self.assertIsNone(core_api.send_dim_command("LGT_NODE_001", 30))

    def test_northbound_command_is_gateway_scoped_and_correlated(self) -> None:
        with patch.object(core_api, "NORTHBOUND_MODE", True):
            cid = core_api.send_dim_command("LGT_NODE_001", 30)
        self.assertIsNotNone(cid)
        self.assertEqual(len(self.client.published), 1)
        sent = self.client.published[0]
        self.assertEqual(sent["topic"], "pccom/v1/t1/s01/gw-001/cmd")
        self.assertEqual((sent["qos"], sent["retain"]), (1, False))

        envelope = parse_envelope(sent["payload"])
        self.assertEqual(envelope["category"], "cmd")
        self.assertEqual(envelope["command_id"], cid)
        self.assertEqual(envelope["action"], "DIM")
        self.assertEqual(envelope["requested_value"], 30)
        self.assertEqual(envelope["data"]["requested_value"], 30)
        self.assertEqual(envelope["source_site_id"], SITE)
        self.assertEqual(envelope["device_id"], "LGT_NODE_001")

        props = sent["properties"]
        self.assertEqual(props.ResponseTopic, "pccom/v1/t1/s01/gw-001/ack")
        self.assertEqual(props.CorrelationData, cid.encode("utf-8"))
        gateway_key = derive_gateway_key(self.secret, "t1", "s01", "gw-001")
        verified_cid, _, _ = verify_envelope(
            gateway_key, sent["topic"], sent["payload"], props.UserProperty
        )
        self.assertEqual(verified_cid, cid)
        device_key = derive_device_key(self.secret, SITE, "light", "LGT_NODE_001")
        with self.assertRaises(SignatureError):
            verify_envelope(device_key, sent["topic"], sent["payload"], props.UserProperty)


@unittest.skipUnless(
    os.environ.get("PCCOM_RUN_CHARACTERIZATION") == "1",
    "Non-normative characterization; enable PCCOM_RUN_CHARACTERIZATION=1",
)
class DimHandlerCharacterizationTests(CoreApiHarness):
    """O-API-HTTP: ghi lại hành vi hiện tại của do_POST, KHÔNG phải acceptance.

    Các test dưới đây chỉ chứng minh implementation làm gì tại revision được kiểm.
    Chúng không khẳng định broadcast cho target không xác định, ghi state trước
    validation hoặc trả SUCCESS khi publish thất bại là hành vi đúng. Khi BE/TL chốt
    policy, các assertion này phải được thay bằng assertion acceptance.
    """

    def install_dispatch(self, failing=()) -> FakeDispatch:
        dispatch = FakeDispatch(failing)
        self._patch(patch.object(core_api, "send_dim_command", dispatch))
        return dispatch

    def reset(self, dispatch: FakeDispatch | None = None) -> None:
        core_api.ASSET_STATE.clear()
        core_api.ASSET_STATE.update(copy.deepcopy(self.assets))
        self.client.published.clear()
        if dispatch is not None:
            dispatch.calls.clear()

    def test_wrong_route_returns_404_without_side_effects(self) -> None:
        dispatch = self.install_dispatch()
        before = self.state()
        status, body = self.post({"asset_id": "LGT_NODE_001", "brightness": 30}, "/api/v1/other")
        self.assertEqual((status, body), (404, None))
        self.assertEqual(dispatch.calls, [])
        self.assertEqual(self.state(), before)

    def test_characterize_known_asset_dispatches_once_and_updates_only_that_asset(self) -> None:
        dispatch = self.install_dispatch()
        before = self.state()
        status, body = self.post({"asset_id": "LGT_NODE_001", "brightness": 30})

        self.assertEqual(status, 200)
        self.assertEqual(dispatch.calls, [("LGT_NODE_001", 30)])
        self.assertEqual(body["status"], "SUCCESS")
        self.assertEqual(body["command_id"], "cid-LGT_NODE_001")
        self.assertEqual(body["correlation_ids"], ["cid-LGT_NODE_001"])
        self.assertEqual((body["affected_nodes"], body["published_nodes"]), (1, 1))
        self.assertEqual(body["brightness"], 30)

        after = self.state()
        self.assertEqual(after["LGT_NODE_001"]["brightness"], 30)
        self.assertEqual(after["LGT_NODE_001"]["power_w"], 30.0)
        for asset_id in ("LGT_NODE_002", NOT_IN_CONFIG):
            self.assertEqual(after[asset_id], before[asset_id])

    def test_characterize_unknown_asset_id_fans_out_to_every_known_asset(self) -> None:
        dispatch = self.install_dispatch()
        status, body = self.post({"asset_id": "NOPE", "brightness": 20})

        self.assertEqual(status, 200)
        self.assertEqual(
            sorted(call[0] for call in dispatch.calls), sorted(self.assets)
        )
        self.assertEqual(body["command_id"], "BROADCAST")
        self.assertEqual((body["affected_nodes"], body["published_nodes"]), (3, 3))
        for asset in self.state().values():
            self.assertEqual(asset["brightness"], 20)

    def test_characterize_missing_all_and_non_light_ids_also_fan_out(self) -> None:
        dispatch = self.install_dispatch()
        bodies = {
            "asset_id omitted": {"brightness": 20},
            "asset_id ALL": {"asset_id": "ALL", "brightness": 20},
            "asset_id empty": {"asset_id": "", "brightness": 20},
            "led display id": {"asset_id": "DSP_LED_001", "brightness": 20},
        }
        for label, request in bodies.items():
            with self.subTest(case=label):
                self.reset(dispatch)
                status, body = self.post(request)
                self.assertEqual(status, 200)
                self.assertEqual(len(dispatch.calls), len(self.assets))
                self.assertEqual(body["affected_nodes"], len(self.assets))

    def test_characterize_out_of_range_brightness_is_written_to_state_but_not_published(
        self,
    ) -> None:
        for value in (150, -5):
            with self.subTest(brightness=value):
                self.reset()
                status, body = self.post({"asset_id": "LGT_NODE_001", "brightness": value})
                self.assertEqual(status, 200)
                self.assertEqual(self.client.published, [])
                self.assertEqual(body["status"], "SUCCESS")
                self.assertEqual((body["affected_nodes"], body["published_nodes"]), (1, 0))
                self.assertEqual(body["correlation_ids"], [])
                state = self.state()["LGT_NODE_001"]
                self.assertEqual(state["brightness"], value)
                self.assertEqual(state["power_w"], round(value / 100.0 * 100.0, 1))

    def test_characterize_asset_missing_from_device_config_is_counted_but_not_published(
        self,
    ) -> None:
        status, body = self.post({"asset_id": NOT_IN_CONFIG, "brightness": 25})
        self.assertEqual(status, 200)
        self.assertEqual(self.client.published, [])
        self.assertEqual(body["status"], "SUCCESS")
        self.assertEqual((body["affected_nodes"], body["published_nodes"]), (1, 0))
        self.assertEqual(self.state()[NOT_IN_CONFIG]["brightness"], 25)

    def test_characterize_failed_publish_still_reports_success_status(self) -> None:
        dispatch = self.install_dispatch(failing={"LGT_NODE_002"})
        status, body = self.post({"asset_id": "NOPE", "brightness": 20})
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "SUCCESS")
        self.assertEqual((body["affected_nodes"], body["published_nodes"]), (3, 2))
        self.assertNotIn("cid-LGT_NODE_002", body["correlation_ids"])
        self.assertEqual(len(dispatch.calls), 3)
        self.assertEqual(self.state()["LGT_NODE_002"]["brightness"], 20)

        self.reset(dispatch)
        dispatch.failing = {"LGT_NODE_001"}
        status, body = self.post({"asset_id": "LGT_NODE_001", "brightness": 20})
        self.assertEqual(body["status"], "SUCCESS")
        self.assertEqual((body["affected_nodes"], body["published_nodes"]), (1, 0))
        self.assertEqual(body["command_id"], "BROADCAST")

    def test_response_counts_and_command_id_are_internally_consistent(self) -> None:
        scenarios = {
            "single ok": ({"asset_id": "LGT_NODE_001", "brightness": 10}, ()),
            "single failed": ({"asset_id": "LGT_NODE_001", "brightness": 10}, ("LGT_NODE_001",)),
            "unknown ok": ({"asset_id": "NOPE", "brightness": 10}, ()),
            "unknown partial": ({"asset_id": "NOPE", "brightness": 10}, ("LGT_NODE_999",)),
            "unknown all failed": ({"asset_id": "NOPE", "brightness": 10}, tuple(self.assets)),
        }
        for label, (request, failing) in scenarios.items():
            with self.subTest(case=label):
                self.reset()
                self._patch(patch.object(core_api, "send_dim_command", FakeDispatch(failing)))
                status, body = self.post(request)
                self.assertEqual(status, 200)
                cids = body["correlation_ids"]
                self.assertEqual(body["published_nodes"], len(cids))
                self.assertLessEqual(body["published_nodes"], body["affected_nodes"])
                self.assertEqual(len(set(cids)), len(cids))
                expected_command_id = cids[0] if len(cids) == 1 else "BROADCAST"
                self.assertEqual(body["command_id"], expected_command_id)

    def test_characterize_malformed_requests_raise_before_any_side_effect(self) -> None:
        dispatch = self.install_dispatch()
        before = self.state()
        cases = {
            "invalid json": (b"not json", json.JSONDecodeError),
            "json array body": (b"[]", AttributeError),
            "non numeric brightness": (
                json.dumps({"asset_id": "LGT_NODE_001", "brightness": "abc"}).encode(),
                ValueError,
            ),
            "null brightness": (
                json.dumps({"asset_id": "LGT_NODE_001", "brightness": None}).encode(),
                TypeError,
            ),
            "missing content length": (None, TypeError),
        }
        for label, (raw, expected) in cases.items():
            with self.subTest(case=label):
                handler = self.make_handler(ROUTE, raw)
                with self.assertRaises(expected):
                    handler.do_POST()
                self.assertEqual(handler.wfile.getvalue(), b"")
                self.assertEqual(dispatch.calls, [])
                self.assertEqual(self.state(), before)


if __name__ == "__main__":
    unittest.main()
