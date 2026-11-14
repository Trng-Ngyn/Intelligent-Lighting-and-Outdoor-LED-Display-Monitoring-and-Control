"""Công cụ dòng lệnh kiểm thử giao thức MQTT 5.

Vị trí trong luồng: đóng vai Cloud/probe độc lập khi cần kiểm thử nhanh mà
không chạy toàn bộ mock_cloud_service.py. Công cụ có thể:
- watch: subscribe và xác thực telemetry/status/alerts/result.
- watch --status-only: theo dõi online/offline để đo LWT.
- send-dim: gửi lệnh dim đã ký tới một thiết bị.
- clear-status: xóa retained status của site/thiết bị.

Ví dụ:
    python tools/mqtt5_probe.py watch --config config.json --status-only
    python tools/mqtt5_probe.py send-dim --config config.json \
        --device LGT_NODE_001 --value 65

Xem docs/specifications/MQTT5_COMMUNICATION_PROTOCOL.md.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional, Sequence

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from edge_simulator.config import ConfigError, DeviceSpec, SimulatorConfig, load_config
from edge_simulator.mqtt_client import Mqtt5Client, MqttConnectionError
from iot_protocol.headers import (
    HeaderError,
    build_headers,
    verify_envelope,
)
from iot_protocol.mqtt5 import (
    COMMAND_MESSAGE_EXPIRY_SEC,
    CONTENT_TYPE_JSON,
    CONTENT_TYPE_TEXT,
    make_connect_properties,
    make_publish_properties,
)
from iot_protocol.signing import (
    ReplayError,
    ReplayGuard,
    SignatureError,
    derive_device_key,
    new_correlation_id,
)
from iot_protocol.topics import (
    alerts_wildcard,
    command_dim_topic,
    command_result_topic,
    command_result_wildcard,
    parse_topic,
    status_topic,
    status_wildcard,
    telemetry_wildcard,
)

LOGGER_NAME = "mqtt5_probe"


def _configure_utf8_streams() -> None:
    """Buộc stdout/stderr dùng UTF-8 để log tiếng Việt không bị escape."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")


def configure_logging(level: str) -> None:
    """Log kèm mili-giây để đo chính xác thời điểm online/offline."""
    _configure_utf8_streams()
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=(
            "%(asctime)s.%(msecs)03d %(levelname)s %(name)s %(message)s"
        ),
        datefmt="%Y-%m-%dT%H:%M:%S",
        force=True,
    )


class Probe:
    """Probe MQTT 5 dùng chung cho các lệnh watch/send-dim/clear-status."""

    def __init__(self, config: SimulatorConfig, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger
        self.devices: dict[tuple[str, str, str], DeviceSpec] = config.device_index()
        self.secrets = {
            key: derive_device_key(
                config.security.signing_secret,
                spec.site_id,
                spec.device_type,
                spec.device_id,
            )
            for key, spec in self.devices.items()
        }
        self.guards = {
            key: ReplayGuard(window_ms=config.settings.replay_window_ms)
            for key in self.devices
        }
        self.client = Mqtt5Client(
            config.broker,
            f"probe-{config.broker.client_id_prefix}",
            logger,
        )
        self.client.set_callbacks(
            on_connect=self._handle_connect,
            on_message=self._handle_message,
        )
        self.status_only = False

    def start(self, status_only: bool = False) -> None:
        """Kết nối broker và subscribe theo chế độ."""
        self.status_only = status_only
        self.client.connect(
            keep_alive_sec=self.config.settings.keep_alive_sec,
            connect_properties=make_connect_properties(),
        )

    def _handle_connect(self) -> None:
        """Subscribe wildcard tương ứng chế độ watch."""
        topics = [status_wildcard()]
        if not self.status_only:
            topics.extend(
                [
                    telemetry_wildcard(),
                    alerts_wildcard(),
                    command_result_wildcard(),
                ]
            )
        for topic in topics:
            self.client.subscribe(topic, qos=1)

    def _handle_message(self, message: object) -> None:
        """Xác thực và in message theo loại."""
        try:
            parsed = parse_topic(message.topic)
        except ValueError as exc:
            self.logger.warning("Topic không hợp lệ topic=%s error=%s", message.topic, exc)
            return

        key = (parsed.site_id, parsed.device_type, parsed.device_id)
        secret = self.secrets.get(key)
        if secret is None:
            self.logger.warning(
                "Thiết bị không có trong config topic=%s", message.topic
            )
            return

        payload_bytes = bytes(message.payload)
        raw_props = getattr(message.properties, "UserProperty", None)
        enforce_ts = parsed.category != "status"
        try:
            cid, ts_ms, _ = verify_envelope(
                secret,
                message.topic,
                payload_bytes,
                raw_props,
                replay_guard=self.guards[key] if enforce_ts else None,
                enforce_timestamp=enforce_ts,
            )
        except HeaderError as exc:
            self.logger.warning(
                "PROBE_REJECT topic=%s reason=HEADER error=%s",
                message.topic,
                exc,
            )
            return
        except SignatureError as exc:
            self.logger.warning(
                "PROBE_REJECT topic=%s reason=SIGNATURE error=%s",
                message.topic,
                exc,
            )
            return
        except ReplayError as exc:
            self.logger.warning(
                "PROBE_REJECT topic=%s reason=REPLAY error=%s",
                message.topic,
                exc,
            )
            return

        payload_text = payload_bytes.decode("utf-8", errors="replace")
        if parsed.category == "status":
            self.logger.info(
                "PROBE_STATUS topic=%s payload=%s correlation_id=%s ts_ms=%s",
                message.topic,
                payload_text,
                cid,
                ts_ms,
            )
        elif parsed.category == "telemetry":
            try:
                data = json.loads(payload_text)
            except json.JSONDecodeError:
                self.logger.warning(
                    "PROBE_TELEMETRY_INVALID topic=%s correlation_id=%s",
                    message.topic,
                    cid,
                )
                return
            self.logger.info(
                "PROBE_TELEMETRY device=%s seq=%s power_w=%s "
                "correlation_id=%s ts_ms=%s",
                data.get("asset_id"),
                data.get("sequence"),
                data.get("metrics", {}).get("power_w"),
                cid,
                ts_ms,
            )
        elif parsed.category == "command_result":
            try:
                data = json.loads(payload_text)
            except json.JSONDecodeError:
                data = {}
            self.logger.info(
                "PROBE_RESULT device=%s command_id=%s status=%s "
                "correlation_id=%s ts_ms=%s",
                data.get("asset_id"),
                data.get("command_id"),
                data.get("status"),
                cid,
                ts_ms,
            )
        elif parsed.category == "alerts":
            try:
                data = json.loads(payload_text)
            except json.JSONDecodeError:
                data = {}
            self.logger.warning(
                "PROBE_ALERT device=%s code=%s correlation_id=%s ts_ms=%s",
                data.get("device_id"),
                data.get("alert_code"),
                cid,
                ts_ms,
            )

    def find_device(
        self,
        device_id: str,
        site_id: Optional[str] = None,
        device_type: Optional[str] = None,
    ) -> DeviceSpec:
        """Tìm thiết bị theo device_id (và site/type nếu cần)."""
        matches = [
            spec
            for spec in self.devices.values()
            if spec.device_id == device_id
            and (site_id is None or spec.site_id == site_id)
            and (device_type is None or spec.device_type == device_type)
        ]
        if not matches:
            raise ConfigError(f"Không tìm thấy thiết bị {device_id}")
        if len(matches) > 1:
            raise ConfigError(
                f"device_id {device_id} xuất hiện ở nhiều site/type; "
                "hãy truyền --site/--type"
            )
        return matches[0]

    def send_dim(self, spec: DeviceSpec, value: int) -> None:
        """Gửi lệnh dim có ký và chờ một nhịp để nhận phản hồi."""
        if value < 0 or value > 100:
            raise ConfigError("--value phải trong [0, 100]")

        topic = command_dim_topic(
            spec.site_id,
            spec.device_type,
            spec.device_id,
        )
        result_topic = command_result_topic(
            spec.site_id,
            spec.device_type,
            spec.device_id,
        )
        cid = new_correlation_id()
        now = int(time.time())
        payload_obj = {
            "command_id": cid,
            "actor": "MQTT5_Probe",
            "action": "DIM",
            "requested_value": value,
            "policy_version": "v1.0",
            "issued_at": now,
            "expires_at": now + COMMAND_MESSAGE_EXPIRY_SEC,
            "priority": 1,
        }
        payload = json.dumps(
            payload_obj,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        secret = self.secrets[spec.key]
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
        ok = self.client.publish(
            topic,
            payload,
            qos=1,
            retain=False,
            properties=props,
        )
        self.logger.info(
            "PROBE_COMMAND_TX device=%s value=%s topic=%s "
            "correlation_id=%s ts_ms=%s ok=%s",
            spec.device_id,
            value,
            topic,
            cid,
            ts_ms,
            ok,
        )

    def clear_status(
        self,
        spec: DeviceSpec,
    ) -> None:
        """Xóa retained status bằng payload rỗng (chuẩn MQTT 5)."""
        topic = status_topic(
            spec.site_id,
            spec.device_type,
            spec.device_id,
        )
        payload = b""
        headers, cid, ts_ms = build_headers(
            self.secrets[spec.key],
            topic,
            payload,
        )
        props = make_publish_properties(
            headers,
            content_type=CONTENT_TYPE_TEXT,
            correlation_data=cid.encode("utf-8"),
        )
        ok = self.client.publish(
            topic,
            payload,
            qos=1,
            retain=True,
            properties=props,
        )
        self.logger.info(
            "PROBE_CLEAR_STATUS device=%s topic=%s correlation_id=%s "
            "ts_ms=%s ok=%s",
            spec.device_id,
            topic,
            cid,
            ts_ms,
            ok,
        )

    def stop(self) -> None:
        """Ngắt kết nối probe."""
        self.client.stop()


def build_parser() -> argparse.ArgumentParser:
    """Tạo parser với các subcommand watch/send-dim/clear-status."""
    parser = argparse.ArgumentParser(description="MQTT 5 probe cho PCCOM")
    parser.add_argument(
        "--config",
        help="Đường dẫn config JSON dùng chung với simulator",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    watch = subparsers.add_parser("watch", help="Subscribe và xác thực message")
    watch.add_argument(
        "--status-only",
        action="store_true",
        help="Chỉ theo dõi status (dùng để đo LWT)",
    )
    watch.add_argument(
        "--run-seconds",
        type=float,
        default=None,
        help="Tự dừng sau N giây",
    )

    send = subparsers.add_parser("send-dim", help="Gửi lệnh dim có ký")
    send.add_argument("--device", required=True, help="device_id đích")
    send.add_argument("--value", type=int, required=True, help="Độ sáng 0-100")
    send.add_argument("--site", help="Lọc theo site_id nếu trùng device_id")
    send.add_argument("--type", dest="device_type", help="Lọc theo device_type")

    clear = subparsers.add_parser(
        "clear-status",
        help="Xóa retained status của một hoặc mọi thiết bị",
    )
    clear.add_argument("--device", help="Chỉ xóa một device_id")
    clear.add_argument("--site", help="Lọc theo site_id")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Hàm main của probe."""
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"[CONFIG ERROR] {exc}", file=sys.stderr)
        return 2

    configure_logging(args.log_level)
    logger = logging.getLogger(LOGGER_NAME)
    probe = Probe(config, logger)
    try:
        if args.command == "watch":
            probe.start(status_only=args.status_only)
            if args.run_seconds is not None:
                if args.run_seconds <= 0:
                    logger.error("--run-seconds phải > 0")
                    return 2
                time.sleep(args.run_seconds)
            else:
                while True:
                    time.sleep(1.0)
        elif args.command == "send-dim":
            spec = probe.find_device(
                args.device,
                site_id=args.site,
                device_type=args.device_type,
            )
            probe.start(status_only=False)
            probe.send_dim(spec, args.value)
            time.sleep(2.0)
        elif args.command == "clear-status":
            probe.start(status_only=False)
            if args.device:
                specs = [
                    probe.find_device(
                        args.device,
                        site_id=args.site,
                    )
                ]
            else:
                specs = [
                    spec
                    for spec in probe.devices.values()
                    if args.site is None or spec.site_id == args.site
                ]
            for spec in specs:
                probe.clear_status(spec)
            time.sleep(1.0)
    except KeyboardInterrupt:
        logger.info("Nhận Ctrl+C, dừng probe...")
    except (ConfigError, MqttConnectionError) as exc:
        logger.error("Probe lỗi: %s", exc)
        return 1
    finally:
        probe.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
