"""AUTO-G1-010 - Backend Read Integration tests cho Core API (GET endpoints).

Phạm vi: kiểm thử cô lập ``backend.core_api.CoreApiHandler.do_GET`` trên hai route
``GET /api/v1/assets`` và ``GET /api/v1/summary`` bằng in-memory HTTP handler
harness, synthetic fixtures và patch global state. Không khởi động broker/server
mạng, không gọi MQTT thật, không đụng thiết bị vật lý và không sửa hai test
module Batch 1 đã được QA chấp nhận.

Test Oracle:
- O-READ-API (ĐÃ XÁC LẬP cho phạm vi demo read handler): ``src/backend/core_api.py``
  (lines 381-451) và hợp đồng tiêu thụ của ``src/frontend/index.html``:
  * ``GET /api/v1/assets`` trả HTTP 200, ``Content-Type: application/json``, CORS
    headers, danh sách ``lighting_nodes`` / ``led_displays``, bộ đếm ``total_lights``
    / ``total_leds`` và ``timestamp`` nguyên theo clock.
  * ``GET /api/v1/summary`` trả HTTP 200, ``Content-Type: application/json``, các
    trường tổng hợp ``total_lights``, ``online_lights``, ``total_power_kw``,
    ``avg_brightness`` nhất quán với ``ASSET_STATE``.
  * Route API không tồn tại trả HTTP 404; thao tác đọc không gây side effect lên
    state, không gọi command dispatch và không publish MQTT.
- O-CHAR (CHỈ GHI NHẬN HIỆN TRẠNG - KHÔNG PHẢI ACCEPTANCE): lớp
  ``CoreApiReadCharacterizationTests`` (mặc định skip; bật opt-in qua biến môi
  trường ``PCCOM_RUN_CHARACTERIZATION=1``) ghi lại hành vi ở các điểm chưa có hợp
  đồng nghiệm thu được phê duyệt (empty ``ASSET_STATE`` gây ``ZeroDivisionError``
  trên ``/api/v1/summary``, làm tròn số thực nhị phân, ``led_status`` /
  ``gate_status`` cứng, query-string rơi xuống ``SimpleHTTPRequestHandler`` 404
  HTML, và nguy cơ lộ file tĩnh từ ``handler.directory``).

Giới hạn truy vết (LGT 01, DSP 01; TS-G1-LGT-01, TS-G1-DSP-01; TC-G1-LGT-01-001,
TC-G1-DSP-01-001): demo read API không bao phủ full asset CRUD, phân quyền theo
tenant/site hay đồng bộ telemetry thời gian thực.
"""

from __future__ import annotations

import copy
from decimal import Decimal
import http.client
import io
import json
import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from backend import core_api

# Bản chụp bất biến của seed mặc định khi nạp module để kiểm tra tính duy nhất ID.
SEED_LIGHTS_SNAPSHOT = copy.deepcopy(core_api.ASSET_STATE)
SEED_LEDS_SNAPSHOT = copy.deepcopy(core_api.LED_DISPLAYS)

FIXED_EPOCH = 1_700_000_123.7

SYNTHETIC_LIGHTS = {
    "LGT_SYN_001": {
        "asset_id": "LGT_SYN_001",
        "site_id": "SITE_SYN_01",
        "name": "Đèn thử nghiệm #1",
        "lat": 10.8510,
        "lng": 106.7720,
        "brightness": 20,
        "relay": True,
        "power_w": 50.0,
        "voltage_v": 220.0,
        "temp_c": 35.0,
        "status": "ONLINE",
    },
    "LGT_SYN_002": {
        "asset_id": "LGT_SYN_002",
        "site_id": "SITE_SYN_01",
        "name": "Đèn thử nghiệm #2",
        "lat": 10.8520,
        "lng": 106.7730,
        "brightness": 60,
        "relay": True,
        "power_w": 75.0,
        "voltage_v": 220.5,
        "temp_c": 36.5,
        "status": "ONLINE",
    },
    "LGT_SYN_003": {
        "asset_id": "LGT_SYN_003",
        "site_id": "SITE_SYN_02",
        "name": "Đèn thử nghiệm #3",
        "lat": 10.8530,
        "lng": 106.7740,
        "brightness": 100,
        "relay": True,
        "power_w": 125.0,
        "voltage_v": 219.8,
        "temp_c": 39.0,
        "status": "ONLINE",
    },
    "LGT_SYN_004": {
        "asset_id": "LGT_SYN_004",
        "site_id": "SITE_SYN_02",
        "name": "Đèn thử nghiệm #4 (ngoại tuyến)",
        "lat": 10.8540,
        "lng": 106.7750,
        "brightness": 20,
        "relay": False,
        "power_w": 0.0,
        "voltage_v": 0.0,
        "temp_c": 30.0,
        "status": "OFFLINE",
    },
}

SYNTHETIC_LEDS = [
    {
        "id": "DSP_SYN_001",
        "name": "Bảng LED thử nghiệm Cổng Bắc",
        "lat": 10.8601,
        "lng": 106.7801,
        "resolution": "1920x1080",
        "current_playlist": "Thông báo phân luồng giao thông",
        "status": "ONLINE",
        "brightness": 80,
    },
    {
        "id": "DSP_SYN_002",
        "name": "Bảng LED thử nghiệm Cổng Nam",
        "lat": 10.8650,
        "lng": 106.7850,
        "resolution": "3840x2160",
        "current_playlist": "Bản tin an toàn đô thị",
        "status": "OFFLINE",
        "brightness": 0,
    },
]


class SpyMqttClient:
    """Test double theo dõi mọi lời gọi publish trong suốt thao tác đọc."""

    def __init__(self) -> None:
        self.published: list[dict] = []

    def publish(self, topic, payload, qos=0, retain=False, properties=None):
        self.published.append(
            dict(
                topic=topic,
                payload=payload,
                qos=qos,
                retain=retain,
                properties=properties,
            )
        )
        return True


class SpyDispatch:
    """Spy chắn hàm send_dim_command để chứng minh GET không phát lệnh."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def __call__(self, asset_id: str, brightness: int):
        self.calls.append((asset_id, brightness))
        return f"unexpected-{asset_id}"


def _independent_summary(lights: list[dict]) -> dict[str, int | float]:
    """Tính độc lập các chỉ số summary bằng số học chính xác trên danh sách fixture."""
    total_lights = len(lights)
    online_lights = sum(1 for item in lights if item["status"] == "ONLINE")
    power_kw = sum(Decimal(str(item["power_w"])) for item in lights) / Decimal("1000")
    avg_brightness = sum(
        Decimal(str(item["brightness"])) for item in lights
    ) / Decimal(total_lights)
    return {
        "total_lights": total_lights,
        "online_lights": online_lights,
        "total_power_kw": float(power_kw),
        "avg_brightness": float(avg_brightness),
    }


class CoreApiReadHarness(unittest.TestCase):
    """Cô lập hoàn toàn state, filesystem fallback và mạng cho mỗi test case."""

    def setUp(self) -> None:
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)

        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.mqtt_spy = SpyMqttClient()
        self.dispatch_spy = SpyDispatch()
        self.lights = copy.deepcopy(SYNTHETIC_LIGHTS)
        self.leds = copy.deepcopy(SYNTHETIC_LEDS)

        self._patch(patch.dict(core_api.ASSET_STATE, self.lights, clear=True))
        self._patch(patch.object(core_api, "LED_DISPLAYS", self.leds))
        self._patch(patch.object(core_api, "MQTT_CLIENT", self.mqtt_spy))
        self._patch(patch.object(core_api, "send_dim_command", self.dispatch_spy))
        self._patch(patch.object(core_api.CoreApiHandler, "log_message"))
        self._patch(patch.object(core_api.CoreApiHandler, "log_error"))
        self._patch(
            patch("socket.socket.connect", side_effect=AssertionError("network access"))
        )

    def _patch(self, patcher):
        started = patcher.start()
        self.addCleanup(patcher.stop)
        return started

    def make_get_handler(self, path: str) -> core_api.CoreApiHandler:
        handler = core_api.CoreApiHandler.__new__(core_api.CoreApiHandler)
        handler.directory = self.temp_dir.name
        handler.path = path
        handler.command = "GET"
        handler.request_version = "HTTP/1.1"
        handler.requestline = f"GET {path} HTTP/1.1"
        handler.client_address = ("127.0.0.1", 0)
        handler.headers = http.client.HTTPMessage()
        handler.rfile = io.BytesIO(b"")
        handler.wfile = io.BytesIO()
        return handler

    @staticmethod
    def parse_raw_http(raw: bytes) -> tuple[int, http.client.HTTPMessage, bytes]:
        head, _, body = raw.partition(b"\r\n\r\n")
        lines = head.split(b"\r\n")
        status = int(lines[0].split(b" ", 2)[1])
        header_bytes = b"\r\n".join(lines[1:]) + b"\r\n\r\n"
        headers = http.client.parse_headers(io.BytesIO(header_bytes))
        return status, headers, body

    def get(self, path: str) -> tuple[int, http.client.HTTPMessage, bytes]:
        handler = self.make_get_handler(path)
        handler.do_GET()
        return self.parse_raw_http(handler.wfile.getvalue())

    def get_json(self, path: str) -> tuple[int, http.client.HTTPMessage, dict]:
        status, headers, body = self.get(path)
        return status, headers, json.loads(body.decode("utf-8"))


class CoreApiReadVerificationTests(CoreApiReadHarness):
    """O-READ-API: kiểm chứng các hành vi đọc có Test Oracle rõ ràng."""

    def test_get_assets_returns_200_json_content_type_and_cors_headers(self) -> None:
        with patch.object(core_api.time, "time", return_value=FIXED_EPOCH):
            status, headers, payload = self.get_json("/api/v1/assets")

        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["Access-Control-Allow-Origin"], "*")
        self.assertIn("GET", headers["Access-Control-Allow-Methods"])
        self.assertEqual(
            set(payload.keys()),
            {"lighting_nodes", "led_displays", "total_lights", "total_leds", "timestamp"},
        )
        self.assertEqual(payload["timestamp"], 1_700_000_123)

    def test_get_assets_matches_synthetic_fixture_ids_and_metadata(self) -> None:
        status, _, payload = self.get_json("/api/v1/assets")
        self.assertEqual(status, 200)
        self.assertEqual(payload["total_lights"], len(SYNTHETIC_LIGHTS))
        self.assertEqual(payload["total_leds"], len(SYNTHETIC_LEDS))

        lights_by_id = {node["asset_id"]: node for node in payload["lighting_nodes"]}
        leds_by_id = {led["id"]: led for led in payload["led_displays"]}
        self.assertEqual(lights_by_id, SYNTHETIC_LIGHTS)
        self.assertEqual(leds_by_id, {led["id"]: led for led in SYNTHETIC_LEDS})

    def test_asset_inventory_contains_no_duplicate_ids(self) -> None:
        _, _, payload = self.get_json("/api/v1/assets")
        inventories = {
            "synthetic_response": (payload["lighting_nodes"], payload["led_displays"]),
            "module_default_seed": (
                list(SEED_LIGHTS_SNAPSHOT.values()),
                SEED_LEDS_SNAPSHOT,
            ),
        }
        for label, (lights, leds) in inventories.items():
            with self.subTest(inventory=label):
                light_ids = [item["asset_id"] for item in lights]
                led_ids = [item["id"] for item in leds]
                self.assertEqual(len(light_ids), len(set(light_ids)))
                self.assertEqual(len(led_ids), len(set(led_ids)))
                self.assertTrue(set(light_ids).isdisjoint(led_ids))

    def test_get_summary_returns_200_json_and_matches_independent_aggregates(self) -> None:
        scenarios = {
            "mixed_online_offline": SYNTHETIC_LIGHTS,
            "all_offline_zero_load": {
                "LGT_A": dict(
                    SYNTHETIC_LIGHTS["LGT_SYN_001"],
                    asset_id="LGT_A",
                    status="OFFLINE",
                    power_w=0.0,
                    brightness=0,
                ),
                "LGT_B": dict(
                    SYNTHETIC_LIGHTS["LGT_SYN_002"],
                    asset_id="LGT_B",
                    status="FAULT",
                    power_w=0.0,
                    brightness=0,
                ),
            },
            "single_online_node": {
                "LGT_ONLY": dict(
                    SYNTHETIC_LIGHTS["LGT_SYN_001"],
                    asset_id="LGT_ONLY",
                    status="ONLINE",
                    power_w=100.0,
                    brightness=85,
                ),
            },
        }
        for label, state_map in scenarios.items():
            with self.subTest(scenario=label):
                core_api.ASSET_STATE.clear()
                core_api.ASSET_STATE.update(copy.deepcopy(state_map))
                expected = _independent_summary(list(state_map.values()))

                status, headers, summary = self.get_json("/api/v1/summary")
                self.assertEqual(status, 200)
                self.assertEqual(headers["Content-Type"], "application/json")
                self.assertEqual(summary["total_lights"], expected["total_lights"])
                self.assertEqual(summary["online_lights"], expected["online_lights"])
                self.assertEqual(summary["total_power_kw"], expected["total_power_kw"])
                self.assertEqual(summary["avg_brightness"], expected["avg_brightness"])

    def test_cross_endpoint_consistency_between_assets_and_summary(self) -> None:
        _, _, assets_before = self.get_json("/api/v1/assets")
        _, _, summary_before = self.get_json("/api/v1/summary")

        derived_before = _independent_summary(assets_before["lighting_nodes"])
        self.assertEqual(assets_before["total_lights"], len(assets_before["lighting_nodes"]))
        self.assertEqual(assets_before["total_leds"], len(assets_before["led_displays"]))
        self.assertEqual(summary_before["total_lights"], assets_before["total_lights"])
        self.assertEqual(summary_before["online_lights"], derived_before["online_lights"])
        self.assertEqual(summary_before["total_power_kw"], derived_before["total_power_kw"])
        self.assertEqual(summary_before["avg_brightness"], derived_before["avg_brightness"])

        # Cập nhật state giả lập (số học thập phân tròn chẵn để không phụ thuộc
        # quy tắc làm tròn chưa xác lập) rồi đọc lại cả hai endpoint.
        core_api.ASSET_STATE["LGT_SYN_002"]["power_w"] = 50.0
        core_api.ASSET_STATE["LGT_SYN_003"]["status"] = "OFFLINE"
        core_api.ASSET_STATE["LGT_SYN_003"]["power_w"] = 0.0
        core_api.ASSET_STATE["LGT_SYN_003"]["brightness"] = 0

        _, _, assets_after = self.get_json("/api/v1/assets")
        _, _, summary_after = self.get_json("/api/v1/summary")
        derived_after = _independent_summary(assets_after["lighting_nodes"])
        self.assertEqual(summary_after["online_lights"], 2)
        self.assertEqual(summary_after["online_lights"], derived_after["online_lights"])
        self.assertEqual(summary_after["total_power_kw"], derived_after["total_power_kw"])
        self.assertEqual(summary_after["avg_brightness"], derived_after["avg_brightness"])

    def test_unknown_api_routes_return_404(self) -> None:
        for route in (
            "/api/v1/unknown",
            "/api/v1/assets/LGT_SYN_001",
            "/api/v1/summary/extra",
            "/api/v2/assets",
        ):
            with self.subTest(route=route):
                status, _, _ = self.get(route)
                self.assertEqual(status, 404)

    def test_read_requests_are_side_effect_free_and_never_publish_or_dispatch(self) -> None:
        lights_before = copy.deepcopy(core_api.ASSET_STATE)
        leds_before = copy.deepcopy(core_api.LED_DISPLAYS)

        for route in ("/api/v1/assets", "/api/v1/summary", "/api/v1/unknown"):
            self.get(route)

        self.assertEqual(core_api.ASSET_STATE, lights_before)
        self.assertEqual(core_api.LED_DISPLAYS, leds_before)
        self.assertEqual(self.dispatch_spy.calls, [])
        self.assertEqual(self.mqtt_spy.published, [])

    def test_root_and_index_routes_serve_frontend_html_without_side_effects(self) -> None:
        frontend_index = SRC_ROOT / "frontend" / "index.html"
        self.assertTrue(frontend_index.exists())
        expected_bytes = frontend_index.read_bytes()

        for route in ("/", "/index.html"):
            with self.subTest(route=route):
                status, headers, body = self.get(route)
                self.assertEqual(status, 200)
                self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
                self.assertEqual(body, expected_bytes)
        self.assertEqual(self.dispatch_spy.calls, [])
        self.assertEqual(self.mqtt_spy.published, [])


@unittest.skipUnless(
    os.environ.get("PCCOM_RUN_CHARACTERIZATION") == "1",
    "Non-normative characterization; enable PCCOM_RUN_CHARACTERIZATION=1",
)
class CoreApiReadCharacterizationTests(CoreApiReadHarness):
    """O-CHAR: ghi nhận hành vi hiện trạng & potential defects (KHÔNG phải acceptance)."""

    def test_characterize_summary_empty_asset_state_raises_zero_division_after_200_header(
        self,
    ) -> None:
        # PD-B2-01: core_api.py gửi header 200 OK trước khi tính avg_brightness rồi chia
        # cho len(ASSET_STATE) == 0, gây ZeroDivisionError và để lại body rỗng.
        core_api.ASSET_STATE.clear()
        handler = self.make_get_handler("/api/v1/summary")
        with self.assertRaises(ZeroDivisionError):
            handler.do_GET()
        status, headers, body = self.parse_raw_http(handler.wfile.getvalue())
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(body, b"")

    def test_characterize_assets_empty_collections_return_empty_lists_and_zero_counts(
        self,
    ) -> None:
        core_api.ASSET_STATE.clear()
        core_api.LED_DISPLAYS.clear()
        status, _, payload = self.get_json("/api/v1/assets")
        self.assertEqual(status, 200)
        self.assertEqual(payload["lighting_nodes"], [])
        self.assertEqual(payload["led_displays"], [])
        self.assertEqual((payload["total_lights"], payload["total_leds"]), (0, 0))

    def test_characterize_summary_rounding_and_hardcoded_led_and_gate_status(self) -> None:
        # Kể cả khi mọi màn hình LED đều OFFLINE, summary vẫn trả led_status="NORMAL".
        for led in core_api.LED_DISPLAYS:
            led["status"] = "OFFLINE"
        core_api.ASSET_STATE.clear()
        for idx, (power_w, brightness) in enumerate(((33.3, 33), (33.3, 33), (33.9, 34)), 1):
            node_id = f"LGT_RND_{idx}"
            core_api.ASSET_STATE[node_id] = dict(
                SYNTHETIC_LIGHTS["LGT_SYN_001"],
                asset_id=node_id,
                power_w=power_w,
                brightness=brightness,
                status="ONLINE",
            )

        status, _, summary = self.get_json("/api/v1/summary")
        self.assertEqual(status, 200)
        self.assertEqual(summary["total_power_kw"], 0.1)
        self.assertEqual(summary["avg_brightness"], 33.3)
        self.assertEqual(summary["led_status"], "NORMAL")
        self.assertEqual(summary["gate_status"], "GATE G0 READINESS VERIFIED")

    def test_characterize_query_string_on_read_routes_falls_through_to_404_html(self) -> None:
        # PD-B2-02: do_GET so khớp chuỗi tuyệt đối self.path nên query string làm rơi
        # xuống SimpleHTTPRequestHandler và trả HTML 404 thay vì JSON.
        for route in ("/api/v1/assets?site_id=SITE_SYN_01", "/api/v1/summary?view=compact"):
            with self.subTest(route=route):
                status, headers, _ = self.get(route)
                self.assertEqual(status, 404)
                self.assertIn("text/html", headers["Content-Type"])

    def test_characterize_non_api_get_falls_through_to_simple_http_directory_serving(
        self,
    ) -> None:
        # PD-B2-03: kế thừa SimpleHTTPRequestHandler khiến nhánh else phục vụ file trực
        # tiếp từ handler.directory (mặc định là thư mục làm việc khi chạy TCPServer).
        probe_file = Path(self.temp_dir.name) / "synthetic_probe.txt"
        probe_file.write_text("isolated-static-fallback-probe", encoding="utf-8")

        status, _, body = self.get("/synthetic_probe.txt")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"isolated-static-fallback-probe")


if __name__ == "__main__":
    unittest.main()
