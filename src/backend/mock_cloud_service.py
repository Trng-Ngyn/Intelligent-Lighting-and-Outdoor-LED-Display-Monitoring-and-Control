"""Mock Cloud service cho luồng MQTT 5 Simulator -> Broker -> Cloud.

Vị trí trong luồng: subscribe telemetry/status/alerts/result, xác thực User
Properties + chữ ký, gửi lệnh dim đã ký xuống thiết bị. Đây là dịch vụ giả
lập phục vụ kiểm thử end-to-end, không phải Cloud production.

Payload telemetry/command/result giữ nguyên schema hiện có; điểm mới là topic
phân tầng v1 và header MQTT 5.

Cách chạy:
    python src/backend/mock_cloud_service.py --config config.json \
        --dim-device LGT_NODE_001 --dim-value 65 --send-delay 5

Xem docs/specifications/MQTT5_COMMUNICATION_PROTOCOL.md.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from edge_simulator.config import ConfigError, DeviceSpec, SimulatorConfig, load_config
from edge_simulator.mqtt_client import Mqtt5Client, MqttConnectionError
from iot_protocol.headers import (
    ALERT_HEADER_MISSING,
    ALERT_REPLAY_DETECTED,
    ALERT_SIGNATURE_INVALID,
    HeaderError,
    build_headers,
    verify_envelope,
)
from iot_protocol.mqtt5 import (
    COMMAND_MESSAGE_EXPIRY_SEC,
    CONTENT_TYPE_JSON,
    make_connect_properties,
    make_publish_properties,
)
from iot_protocol.signing import (
    ReplayError,
    ReplayGuard,
    SignatureError,
    derive_device_key,
    new_correlation_id,
    now_ms,
)
from iot_protocol.topics import (
    alerts_topic,
    alerts_wildcard,
    command_dim_topic,
    command_result_topic,
    command_result_wildcard,
    parse_topic,
    status_wildcard,
    telemetry_wildcard,
)

LOGGER_NAME = "mock_cloud"


@dataclass
class DeviceState:
    """Trạng thái Cloud lưu cho mỗi thiết bị trong RAM."""

    spec: DeviceSpec
    secret: bytes
    replay_guard: ReplayGuard
    last_status: Optional[str] = None
    last_status_at: Optional[str] = None


def _configure_utf8_streams() -> None:
    """Buộc stdout/stderr dùng UTF-8 để log tiếng Việt không bị escape."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")


def configure_logging(level: str) -> None:
    """Cấu hình log có timestamp mili-giây để đo LWT."""
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
    """Đọc tham số dòng lệnh."""
    parser = argparse.ArgumentParser(
        description="Mock Cloud MQTT 5 cho hệ thống chiếu sáng PCCOM",
    )
    parser.add_argument(
        "--config",
        help="Đường dẫn config JSON dùng chung với simulator",
    )
    parser.add_argument("--dim-device", help="device_id nhận lệnh dim")
    parser.add_argument(
        "--dim-value",
        type=int,
        default=80,
        help="Độ sáng 0-100 (mặc định 80)",
    )
    parser.add_argument(
        "--send-delay",
        type=float,
        default=5.0,
        help="Chờ N giây sau khi kết nối rồi gửi lệnh (mặc định 5)",
    )
    parser.add_argument(
        "--run-seconds",
        type=float,
        help="Tự dừng sau N giây (dùng cho kiểm thử tự động)",
    )
    parser.add_argument(
        "--no-auto-command",
        action="store_true",
        help="Không tự gửi lệnh dim khi khởi động",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
    )
    return parser.parse_args(argv)


class MockCloudService:
    """Dịch vụ Cloud giả lập: xác thực inbound và gửi lệnh dim có ký."""

    def __init__(self, config: SimulatorConfig, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger
        self.devices: dict[tuple[str, str, str], DeviceState] = {}
        for spec in config.devices:
            self.devices[spec.key] = DeviceState(
                spec=spec,
                secret=derive_device_key(
                    config.security.signing_secret,
                    spec.site_id,
                    spec.device_type,
                    spec.device_id,
                ),
                replay_guard=ReplayGuard(
                    window_ms=config.settings.replay_window_ms
                ),
            )

        client_id = f"cloud-{config.broker.client_id_prefix}"
        self.client = Mqtt5Client(config.broker, client_id, logger)
        self.client.set_callbacks(
            on_connect=self._handle_connect,
            on_message=self._handle_message,
        )

    def start(self) -> None:
        """Kết nối broker và chờ CONNACK."""
        self.client.connect(
            keep_alive_sec=self.config.settings.keep_alive_sec,
            connect_properties=make_connect_properties(),
        )

    def _handle_connect(self) -> None:
        """Subscribe các wildcard Cloud cần theo dõi."""
        for topic in (
            telemetry_wildcard(),
            status_wildcard(),
            alerts_wildcard(),
            command_result_wildcard(),
        ):
            self.client.subscribe(topic, qos=1)

    def _handle_message(self, message: object) -> None:
        """Xác thực và phân loại message inbound."""
        topic = message.topic
        try:
            parsed = parse_topic(topic)
        except ValueError as exc:
            self.logger.warning("Bỏ qua topic không hợp lệ topic=%s error=%s", topic, exc)
            return

        state = self.devices.get(
            (parsed.site_id, parsed.device_type, parsed.device_id)
        )
        if state is None:
            self.logger.warning(
                "Bỏ qua thiết bị không có trong config topic=%s", topic
            )
            return

        payload_bytes = bytes(message.payload)
        raw_props = getattr(message.properties, "UserProperty", None)
        enforce_ts = parsed.category != "status"

        try:
            cid, ts_ms, _ = verify_envelope(
                state.secret,
                topic,
                payload_bytes,
                raw_props,
                replay_guard=state.replay_guard if enforce_ts else None,
                enforce_timestamp=enforce_ts,
            )
        except HeaderError as exc:
            self._reject(state, ALERT_HEADER_MISSING, "HIGH", str(exc), topic)
            return
        except SignatureError as exc:
            self._reject(
                state,
                ALERT_SIGNATURE_INVALID,
                "HIGH",
                str(exc),
                topic,
            )
            return
        except ReplayError as exc:
            self._reject(
                state,
                ALERT_REPLAY_DETECTED,
                "HIGH",
                str(exc),
                topic,
            )
            return

        if parsed.category == "status":
            self._handle_status(state, topic, payload_bytes, cid, ts_ms)
        elif parsed.category == "telemetry":
            self._handle_telemetry(topic, payload_bytes, cid, ts_ms)
        elif parsed.category == "command_result":
            self._handle_result(topic, payload_bytes, cid, ts_ms)
        elif parsed.category == "alerts":
            self._handle_alert(topic, payload_bytes, cid, ts_ms)

    def _handle_status(
        self,
        state: DeviceState,
        topic: str,
        payload: bytes,
        cid: str,
        ts_ms: int,
    ) -> None:
        """Ghi nhận online/offline; đây là bằng chứng kiểm thử LWT."""
        status = payload.decode("utf-8", errors="replace")
        timestamp = time.strftime(
            "%Y-%m-%dT%H:%M:%S",
            time.localtime(),
        )
        changed = status != state.last_status
        state.last_status = status
        state.last_status_at = timestamp
        self.logger.info(
            "STATUS_CHANGE device=%s/%s/%s status=%s changed=%s "
            "topic=%s correlation_id=%s ts_ms=%s at=%s",
            state.spec.site_id,
            state.spec.device_type,
            state.spec.device_id,
            status,
            changed,
            topic,
            cid,
            ts_ms,
            timestamp,
        )

    def _handle_telemetry(
        self,
        topic: str,
        payload: bytes,
        cid: str,
        ts_ms: int,
    ) -> None:
        """Log tóm tắt telemetry đã xác thực."""
        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self.logger.warning(
                "Telemetry sai JSON topic=%s correlation_id=%s error=%s",
                topic,
                cid,
                exc,
            )
            return
        metrics = data.get("metrics", {})
        self.logger.info(
            "TELEMETRY device=%s seq=%s power_w=%s voltage_v=%s temp_c=%s "
            "lux=%s topic=%s correlation_id=%s ts_ms=%s",
            data.get("asset_id"),
            data.get("sequence"),
            metrics.get("power_w"),
            metrics.get("voltage_v"),
            metrics.get("temperature_c"),
            metrics.get("ambient_lux"),
            topic,
            cid,
            ts_ms,
        )

    def _handle_result(
        self,
        topic: str,
        payload: bytes,
        cid: str,
        ts_ms: int,
    ) -> None:
        """Log phản hồi lệnh, nhấn mạnh correlation_id dùng chung."""
        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self.logger.warning(
                "Result sai JSON topic=%s correlation_id=%s error=%s",
                topic,
                cid,
                exc,
            )
            return
        self.logger.info(
            "COMMAND_RESULT device=%s command_id=%s status=%s observed=%s "
            "topic=%s correlation_id=%s ts_ms=%s",
            data.get("asset_id"),
            data.get("command_id"),
            data.get("status"),
            data.get("observed_value"),
            topic,
            cid,
            ts_ms,
        )

    def _handle_alert(
        self,
        topic: str,
        payload: bytes,
        cid: str,
        ts_ms: int,
    ) -> None:
        """Log alert do thiết bị phát."""
        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.logger.warning(
                "Alert không phải JSON topic=%s correlation_id=%s",
                topic,
                cid,
            )
            return
        self.logger.warning(
            "ALERT_RX device=%s code=%s severity=%s message=%s topic=%s "
            "correlation_id=%s ts_ms=%s",
            data.get("device_id"),
            data.get("alert_code"),
            data.get("severity"),
            data.get("message"),
            topic,
            cid,
            ts_ms,
        )

    def _reject(
        self,
        state: DeviceState,
        alert_code: str,
        severity: str,
        message: str,
        topic: str,
    ) -> None:
        """Từ chối message và phát alert lên topic của thiết bị."""
        self.logger.warning(
            "REJECT topic=%s device=%s code=%s reason=%s",
            topic,
            state.spec.device_id,
            alert_code,
            message,
        )
        self.publish_alert(state, alert_code, severity, message)

    def publish_alert(
        self,
        state: DeviceState,
        alert_code: str,
        severity: str,
        message: str,
        related_correlation_id: Optional[str] = None,
    ) -> None:
        """Publish alert đã ký bằng khóa của thiết bị liên quan."""
        topic = alerts_topic(
            state.spec.site_id,
            state.spec.device_type,
            state.spec.device_id,
        )
        payload_obj = {
            "schema_version": "1.0.0",
            "alert_code": alert_code,
            "severity": severity,
            "message": message,
            "device_id": state.spec.device_id,
            "ts_ms": now_ms(),
        }
        if related_correlation_id:
            payload_obj["related_correlation_id"] = related_correlation_id
        payload = json.dumps(
            payload_obj,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        headers, cid, ts_ms = build_headers(state.secret, topic, payload)
        props = make_publish_properties(
            headers,
            content_type=CONTENT_TYPE_JSON,
            correlation_data=cid.encode("utf-8"),
        )
        ok = self.client.publish(
            topic,
            payload,
            qos=1,
            retain=False,
            properties=props,
        )
        self.logger.warning(
            "ALERT_TX topic=%s correlation_id=%s ts_ms=%s code=%s ok=%s",
            topic,
            cid,
            ts_ms,
            alert_code,
            ok,
        )

    def send_dim(self, spec: DeviceSpec, value: int) -> None:
        """Gửi lệnh dim MQTT 5 có chữ ký tới một thiết bị.

        Tham số:
            spec: Thiết bị đích.
            value: Độ sáng 0-100.

        Ngoại lệ:
            ValueError: Nếu value ngoài miền.
        """
        if value < 0 or value > 100:
            raise ValueError("dim value phải trong [0, 100]")

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
            "actor": "MockCloud_Operator",
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
        state = self.devices[spec.key]
        headers, _, ts_ms = build_headers(
            state.secret,
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
            "COMMAND_TX device=%s/%s/%s value=%s topic=%s "
            "correlation_id=%s ts_ms=%s response_topic=%s ok=%s",
            spec.site_id,
            spec.device_type,
            spec.device_id,
            value,
            topic,
            cid,
            ts_ms,
            result_topic,
            ok,
        )

    def stop(self) -> None:
        """Ngắt kết nối Cloud."""
        self.client.stop()


def send_dim_later(
    service: MockCloudService,
    spec: DeviceSpec,
    value: int,
    delay_sec: float,
) -> None:
    """Thread gửi lệnh sau delay để chắc chắn thiết bị đã subscribe."""
    time.sleep(delay_sec)
    try:
        service.send_dim(spec, value)
    except Exception:  # pragma: no cover
        service.logger.exception("Gửi lệnh dim thất bại device=%s", spec.device_id)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Hàm main của Mock Cloud."""
    args = parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"[CONFIG ERROR] {exc}", file=sys.stderr)
        return 2

    if args.log_level:
        config = _replace_log_level(config, args.log_level)
    configure_logging(config.settings.log_level)
    logger = logging.getLogger(LOGGER_NAME)

    service = MockCloudService(config, logger)
    try:
        service.start()
    except MqttConnectionError as exc:
        logger.error("Không kết nối được broker: %s", exc)
        return 1

    target: Optional[DeviceSpec] = None
    if args.dim_device:
        for spec in config.devices:
            if spec.device_id == args.dim_device:
                target = spec
                break
        if target is None:
            logger.error("Không tìm thấy thiết bị --dim-device=%s", args.dim_device)
            service.stop()
            return 2
    elif not args.no_auto_command:
        target = config.devices[0]

    if target is not None:
        if args.send_delay <= 0:
            service.send_dim(target, args.dim_value)
        else:
            threading.Thread(
                target=send_dim_later,
                args=(service, target, args.dim_value, args.send_delay),
                name="dim-sender",
                daemon=True,
            ).start()

    try:
        if args.run_seconds is not None:
            if args.run_seconds <= 0:
                logger.error("--run-seconds phải > 0")
                service.stop()
                return 2
            time.sleep(args.run_seconds)
        else:
            while True:
                time.sleep(1.0)
    except KeyboardInterrupt:
        logger.info("Nhận Ctrl+C, dừng Mock Cloud...")
    finally:
        service.stop()
    return 0


def _replace_log_level(
    config: SimulatorConfig,
    level: str,
) -> SimulatorConfig:
    """Ghi đè log level mà không đụng tới các trường khác."""
    from dataclasses import replace

    return replace(
        config,
        settings=replace(config.settings, log_level=level.upper()),
    )


if __name__ == "__main__":
    raise SystemExit(main())
