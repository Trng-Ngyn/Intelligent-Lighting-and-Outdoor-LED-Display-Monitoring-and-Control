"""Core API giả lập: HTTP cho Web Console và cầu nối lệnh dim sang MQTT 5.

Vị trí trong luồng: Web Console -> Core API -> MQTT Broker -> Simulator/ESP32.
File này giữ nguyên các endpoint HTTP hiện có; phần thay đổi là topic phân
tầng v1 và header MQTT 5 khi publish lệnh dim.

Payload lệnh gửi xuống thiết bị giữ nguyên schema cũ. Mỗi thiết bị nhận một
lệnh riêng với correlation_id riêng để phản hồi có thể truy vết chính xác.

Cách chạy:
    python src/backend/core_api.py

Xem docs/specifications/MQTT5_COMMUNICATION_PROTOCOL.md.
"""

from __future__ import annotations

import argparse
import http.server
import json
import logging
import os
import socketserver
import sys
import time
from pathlib import Path
from typing import Optional, Sequence

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from edge_simulator.config import ConfigError, DeviceSpec, SimulatorConfig, load_config
from edge_simulator.mqtt_client import Mqtt5Client, MqttConnectionError
from iot_protocol.headers import build_headers
from iot_protocol.mqtt5 import (
    COMMAND_MESSAGE_EXPIRY_SEC,
    CONTENT_TYPE_JSON,
    make_connect_properties,
    make_publish_properties,
)
from iot_protocol.northbound_payload import (
    build_envelope,
    derive_gateway_key,
    encode_envelope,
)
from iot_protocol.northbound_topics import northbound_topic
from iot_protocol.signing import (
    derive_device_key,
    new_correlation_id,
)
from iot_protocol.topics import command_dim_topic, command_result_topic

HTTP_PORT = 8080
SITE_ID = "SITE_01"
LOGGER_NAME = "core_api"
LOGGER = logging.getLogger(LOGGER_NAME)

MQTT_CLIENT: Optional[Mqtt5Client] = None
RUNTIME_CONFIG: Optional[SimulatorConfig] = None
DEVICE_INDEX: dict[tuple[str, str, str], DeviceSpec] = {}
NORTHBOUND_MODE = False

# Kho luu tru trang thai thiet bi trong RAM (In-memory Asset Cache)
ASSET_STATE = {}
for i in range(1, 51):
    aid = f"LGT_NODE_{i:03d}"
    ASSET_STATE[aid] = {
        "asset_id": aid,
        "site_id": SITE_ID,
        "name": f"Đèn chiếu sáng thông minh #{i}",
        "lat": 10.8505 + (i * 0.0008),
        "lng": 106.7719 + ((i % 5) * 0.001),
        "brightness": 50,
        "relay": True,
        "power_w": 48.5,
        "voltage_v": 220.2,
        "temp_c": 36.5,
        "status": "ONLINE",
    }

# 2 Man hinh LED
LED_DISPLAYS = [
    {
        "id": "DSP_LED_001",
        "name": "Màn hình LED Khu Công Nghệ Cao (Site 01)",
        "lat": 10.8520,
        "lng": 106.7740,
        "resolution": "1920x1080",
        "current_playlist": "Thông điệp an toàn giao thông đô thị",
        "status": "ONLINE",
        "brightness": 80,
    },
    {
        "id": "DSP_LED_002",
        "name": "Màn hình LED Trung tâm Điều hành (Site 02)",
        "lat": 10.8560,
        "lng": 106.7780,
        "resolution": "3840x2160",
        "current_playlist": "Bản tin tuyên truyền chuyển đổi số TP.HCM",
        "status": "ONLINE",
        "brightness": 75,
    },
]


def _configure_utf8_streams() -> None:
    """Buộc stdout/stderr dùng UTF-8 để log tiếng Việt không bị escape."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")


def configure_logging(level: str = "INFO") -> None:
    """Cấu hình logging cho Core API."""
    _configure_utf8_streams()
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=(
            "%(asctime)s.%(msecs)03d %(levelname)s %(name)s %(message)s"
        ),
        datefmt="%Y-%m-%dT%H:%M:%S",
        force=True,
    )


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Đọc tham số dòng lệnh của Core API."""
    parser = argparse.ArgumentParser(
        description="Core API giả lập cho Web Console và MQTT 5",
    )
    parser.add_argument("--config", help="Đường dẫn config JSON")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--northbound",
        action="store_true",
        help="Gửi lệnh qua pccom/v1 (cần gateway bridge)",
    )
    mode.add_argument(
        "--southbound",
        action="store_true",
        help="Gửi trực tiếp topic thiết bị IoT (mặc định)",
    )
    return parser.parse_args(argv)


def init_mqtt(
    northbound: bool = False,
    config_path: Optional[str] = None,
) -> None:
    """Nạp config, tạo client MQTT 5 và kết nối broker.

    Nếu broker/config lỗi, HTTP API vẫn chạy nhưng lệnh dim sẽ không được gửi;
    lỗi được log ở mức ERROR để người vận hành biết.
    """
    global MQTT_CLIENT, RUNTIME_CONFIG, DEVICE_INDEX, NORTHBOUND_MODE

    try:
        config = load_config(config_path)
    except ConfigError as exc:
        LOGGER.error("Không nạp được cấu hình MQTT: %s", exc)
        return

    NORTHBOUND_MODE = northbound

    RUNTIME_CONFIG = config
    DEVICE_INDEX = config.device_index()
    client = Mqtt5Client(
        config.broker,
        client_id=f"backend-core-api-{config.broker.client_id_prefix}",
        logger=LOGGER,
    )
    try:
        client.connect(
            keep_alive_sec=config.settings.keep_alive_sec,
            connect_properties=make_connect_properties(),
        )
    except MqttConnectionError as exc:
        LOGGER.error("Không kết nối được MQTT broker: %s", exc)
        return

    MQTT_CLIENT = client
    LOGGER.info(
        "Core API đã kết nối MQTT 5 broker=%s:%s mode=%s",
        config.broker.host,
        config.broker.port,
        "northbound" if northbound else "southbound",
    )


def _find_light_spec(asset_id: str) -> Optional[DeviceSpec]:
    """Tìm cấu hình thiết bị loại light theo asset_id của Web Console."""
    for spec in DEVICE_INDEX.values():
        if spec.device_id == asset_id and spec.device_type == "light":
            return spec
    return None


def send_dim_command(asset_id: str, brightness: int) -> Optional[str]:
    """Gửi lệnh dim có ký tới một thiết bị.

    Tham số:
        asset_id: Mã tài sản trên Web Console (ví dụ LGT_NODE_001).
        brightness: Độ sáng 0-100.

    Trả về:
        correlation_id/command_id nếu publish thành công, None nếu không.

    Ngoại lệ:
        ValueError: Nếu brightness ngoài miền 0-100.
    """
    if brightness < 0 or brightness > 100:
        raise ValueError("brightness phải trong [0, 100]")
    if MQTT_CLIENT is None or RUNTIME_CONFIG is None:
        LOGGER.error(
            "Chưa kết nối MQTT, không gửi được lệnh asset_id=%s",
            asset_id,
        )
        return None

    spec = _find_light_spec(asset_id)
    if spec is None:
        LOGGER.warning(
            "Không tìm thấy thiết bị trong config asset_id=%s",
            asset_id,
        )
        return None

    if NORTHBOUND_MODE:
        return _send_dim_northbound(spec, brightness)

    topic = command_dim_topic(spec.site_id, spec.device_type, spec.device_id)
    result_topic = command_result_topic(
        spec.site_id,
        spec.device_type,
        spec.device_id,
    )
    cid = new_correlation_id()
    now = int(time.time())
    payload_obj = {
        "command_id": cid,
        "actor": "WebConsole_Operator",
        "action": "DIM",
        "requested_value": brightness,
        "expires_at": now + COMMAND_MESSAGE_EXPIRY_SEC,
    }
    payload = json.dumps(
        payload_obj,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    secret = derive_device_key(
        RUNTIME_CONFIG.security.signing_secret,
        spec.site_id,
        spec.device_type,
        spec.device_id,
    )
    headers, _, ts_ms = build_headers(
        secret,
        topic,
        payload,
        correlation_id=cid,
    )
    props = make_publish_properties(
        headers,
        content_type=CONTENT_TYPE_JSON,
        message_expiry_interval=COMMAND_MESSAGE_EXPIRY_SEC,
        correlation_data=cid.encode("utf-8"),
        response_topic=result_topic,
    )
    ok = MQTT_CLIENT.publish(
        topic,
        payload,
        qos=1,
        retain=False,
        properties=props,
    )
    LOGGER.info(
        "COMMAND_TX asset_id=%s brightness=%s topic=%s correlation_id=%s "
        "ts_ms=%s response_topic=%s ok=%s",
        asset_id,
        brightness,
        topic,
        cid,
        ts_ms,
        result_topic,
        ok,
    )
    return cid if ok else None


def _send_dim_northbound(
    spec: DeviceSpec,
    brightness: int,
) -> Optional[str]:
    """Gửi một lệnh dim qua gateway northbound."""
    if MQTT_CLIENT is None or RUNTIME_CONFIG is None:
        return None

    config = RUNTIME_CONFIG
    gateway = config.gateway_for_site(spec.site_id)
    site_slug = config.northbound_site(spec.site_id)
    tenant = config.northbound.tenant_id
    topic = northbound_topic(tenant, site_slug, gateway, "cmd")
    ack_topic = northbound_topic(tenant, site_slug, gateway, "ack")
    cid = new_correlation_id()
    now = int(time.time())
    expires_at = now + COMMAND_MESSAGE_EXPIRY_SEC
    body = {
        "action": "DIM",
        "requested_value": brightness,
        "actor": "WebConsole_Operator",
        "issued_at": now,
        "expires_at": expires_at,
        "priority": 1,
    }
    envelope = build_envelope(
        tenant_id=tenant,
        site_id=site_slug,
        gateway_id=gateway,
        source_site_id=spec.site_id,
        device_type=spec.device_type,
        device_id=spec.device_id,
        category="cmd",
        data=body,
        extra={
            "command_id": cid,
            "action": "DIM",
            "requested_value": brightness,
            "issued_at": now,
            "expires_at": expires_at,
            "priority": 1,
        },
    )
    payload = encode_envelope(envelope)
    secret = derive_gateway_key(
        config.security.signing_secret,
        tenant,
        site_slug,
        gateway,
    )
    headers, _, ts_ms = build_headers(
        secret,
        topic,
        payload,
        correlation_id=cid,
    )
    props = make_publish_properties(
        headers,
        content_type=CONTENT_TYPE_JSON,
        message_expiry_interval=COMMAND_MESSAGE_EXPIRY_SEC,
        correlation_data=cid.encode("utf-8"),
        response_topic=ack_topic,
    )
    ok = MQTT_CLIENT.publish(
        topic,
        payload,
        qos=1,
        retain=False,
        properties=props,
    )
    LOGGER.info(
        "COMMAND_TX_NB asset_id=%s gateway=%s brightness=%s topic=%s "
        "command_id=%s correlation_id=%s ts_ms=%s response_topic=%s ok=%s",
        spec.device_id,
        gateway,
        brightness,
        topic,
        cid,
        cid,
        ts_ms,
        ack_topic,
        ok,
    )
    return cid if ok else None


class CoreApiHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler giữ nguyên contract API hiện có."""

    def end_headers(self) -> None:
        """Thêm CORS cho Web Console."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        """Trả lời preflight CORS."""
        self.send_response(200)
        self.end_headers()

    def do_GET(self) -> None:
        """Phục vụ danh sách tài sản, summary và frontend tĩnh."""
        if self.path == "/api/v1/assets":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            data = {
                "lighting_nodes": list(ASSET_STATE.values()),
                "led_displays": LED_DISPLAYS,
                "total_lights": len(ASSET_STATE),
                "total_leds": len(LED_DISPLAYS),
                "timestamp": int(time.time()),
            }
            self.wfile.write(
                json.dumps(data, ensure_ascii=False).encode("utf-8")
            )
        elif self.path == "/api/v1/summary":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            total_power = sum(
                item["power_w"] for item in ASSET_STATE.values()
            )
            data = {
                "total_lights": len(ASSET_STATE),
                "online_lights": len(
                    [
                        x
                        for x in ASSET_STATE.values()
                        if x["status"] == "ONLINE"
                    ]
                ),
                "total_power_kw": round(total_power / 1000.0, 2),
                "avg_brightness": round(
                    sum(x["brightness"] for x in ASSET_STATE.values())
                    / len(ASSET_STATE),
                    1,
                ),
                "led_status": "NORMAL",
                "gate_status": "GATE G0 READINESS VERIFIED",
            }
            self.wfile.write(
                json.dumps(data, ensure_ascii=False).encode("utf-8")
            )
        else:
            # Serve frontend files if matching
            frontend_dir = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "frontend")
            )
            if self.path == "/" or self.path == "/index.html":
                filepath = os.path.join(frontend_dir, "index.html")
                if os.path.exists(filepath):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    with open(filepath, "rb") as file_handle:
                        self.wfile.write(file_handle.read())
                    return
            super().do_GET()

    def do_POST(self) -> None:
        """Nhận lệnh dim từ Web Console và publish MQTT 5."""
        if self.path != "/api/v1/controls/dim":
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers["Content-Length"])
        post_data = self.rfile.read(content_length)
        request = json.loads(post_data.decode("utf-8"))

        target_id = request.get("asset_id", "ALL")
        brightness = int(request.get("brightness", 50))

        targets = (
            [target_id]
            if target_id in ASSET_STATE
            else list(ASSET_STATE.keys())
        )
        correlation_ids: list[str] = []
        for target in targets:
            ASSET_STATE[target]["brightness"] = brightness
            ASSET_STATE[target]["power_w"] = round(
                (brightness / 100.0) * 100.0,
                1,
            )
            try:
                cid = send_dim_command(target, brightness)
            except ValueError as exc:
                LOGGER.error("Lệnh dim không hợp lệ target=%s: %s", target, exc)
                cid = None
            if cid:
                correlation_ids.append(cid)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        command_id = (
            correlation_ids[0]
            if len(correlation_ids) == 1
            else "BROADCAST"
        )
        self.wfile.write(
            json.dumps(
                {
                    "status": "SUCCESS",
                    "command_id": command_id,
                    "correlation_ids": correlation_ids,
                    "affected_nodes": len(targets),
                    "published_nodes": len(correlation_ids),
                    "brightness": brightness,
                }
            ).encode("utf-8")
        )


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Khởi động Core API và MQTT client."""
    args = parse_args(argv)
    configure_logging()
    northbound = bool(args.northbound and not args.southbound)
    init_mqtt(northbound=northbound, config_path=args.config)
    LOGGER.info(
        "Core API chạy tại http://localhost:%s (MQTT connected=%s mode=%s)",
        HTTP_PORT,
        MQTT_CLIENT is not None,
        "northbound" if northbound else "southbound",
    )
    with socketserver.TCPServer(("", HTTP_PORT), CoreApiHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            LOGGER.info("Dừng Core API...")
        finally:
            if MQTT_CLIENT is not None:
                MQTT_CLIENT.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
