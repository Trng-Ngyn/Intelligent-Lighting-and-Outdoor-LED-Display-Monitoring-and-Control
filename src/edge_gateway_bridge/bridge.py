"""Bridge gateway hai lớp cho Phương án C.

Southbound:
    telemetry/status/alerts/commands... của từng thiết bị IoT.

Northbound:
    pccom/v1/{tenant}/{site}/{gateway}/{category}
    category = telemetry | cmd | ack | status | alerts

Bridge xác thực envelope southbound bằng khóa thiết bị, map sang canonical
envelope, rồi ký northbound bằng khóa gateway. Chiều lệnh làm ngược lại:
xác thực lệnh northbound bằng khóa gateway, fan-out xuống đúng thiết bị và
ký southbound bằng khóa thiết bị.

Cách chạy:
    python src/edge_gateway_bridge/bridge.py --config config.json
    python src/edge_gateway_bridge/bridge.py --config config.json --site SITE_01
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import queue
import sys
import threading
import time
from pathlib import Path
from typing import Any, Optional, Sequence

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
    make_will_properties,
)
from iot_protocol.northbound_payload import (
    NorthboundPayloadError,
    build_envelope,
    command_target,
    derive_gateway_key,
    encode_envelope,
    normalize_ack_status,
    parse_envelope,
)
from iot_protocol.northbound_topics import northbound_topic
from iot_protocol.signing import (
    ReplayError,
    ReplayGuard,
    SignatureError,
    derive_device_key,
    now_ms,
)
from iot_protocol.topics import (
    TOPIC_VERSION,
    command_dim_topic,
    command_result_topic,
    parse_topic,
    validate_device_type,
)

LOGGER_NAME = "gateway_bridge"


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
    """Đọc tham số dòng lệnh của bridge."""
    parser = argparse.ArgumentParser(
        description="Gateway bridge MQTT 5 southbound IoT -> northbound PCCOM",
    )
    parser.add_argument("--config", help="Đường dẫn config JSON dùng chung")
    parser.add_argument(
        "--site",
        help="Chỉ chạy bridge cho một source site (ví dụ SITE_01)",
    )
    parser.add_argument(
        "--gateway",
        help="Ghi đè gateway_id northbound; cần --site nếu có nhiều site",
    )
    parser.add_argument(
        "--run-seconds",
        type=float,
        help="Tự dừng gracefully sau N giây (dùng cho kiểm thử)",
    )
    parser.add_argument(
        "--crash-after",
        type=float,
        metavar="SECONDS",
        help="Thoát không DISCONNECT sau N giây để kiểm thử LWT gateway",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
    )
    return parser.parse_args(argv)


class GatewayLink:
    """Một kết nối MQTT đại diện cho đúng một gateway/site."""

    def __init__(
        self,
        config: SimulatorConfig,
        source_site: str,
        gateway_id: str,
        logger: logging.Logger,
    ) -> None:
        self.config = config
        self.source_site = source_site
        self.site_slug = config.northbound_site(source_site)
        self.tenant_id = config.northbound.tenant_id
        self.gateway_id = gateway_id
        self.logger = logger
        self.gateway_secret = derive_gateway_key(
            config.security.signing_secret,
            self.tenant_id,
            self.site_slug,
            self.gateway_id,
        )
        self.gateway_guard = ReplayGuard(
            window_ms=config.settings.replay_window_ms
        )

        self.devices: dict[tuple[str, str], DeviceSpec] = {}
        self.device_secrets: dict[tuple[str, str], bytes] = {}
        self.device_guards: dict[tuple[str, str], ReplayGuard] = {}
        for spec in config.devices:
            if spec.site_id != source_site:
                continue
            key = (spec.device_type, spec.device_id)
            self.devices[key] = spec
            self.device_secrets[key] = derive_device_key(
                config.security.signing_secret,
                spec.site_id,
                spec.device_type,
                spec.device_id,
            )
            self.device_guards[key] = ReplayGuard(
                window_ms=config.settings.replay_window_ms
            )

        self.status_topic = northbound_topic(
            self.tenant_id,
            self.site_slug,
            self.gateway_id,
            "status",
        )
        self.command_topic = northbound_topic(
            self.tenant_id,
            self.site_slug,
            self.gateway_id,
            "cmd",
        )

        client_id = (
            f"{config.northbound.client_id_prefix}-"
            f"{self.tenant_id}-{self.site_slug}-{self.gateway_id}"
        )
        self.client = Mqtt5Client(config.broker, client_id, logger)
        self.client.set_callbacks(
            on_connect=self._handle_connect,
            on_message=self._handle_message,
            on_disconnect=self._handle_disconnect,
        )
        # Publish command cần chờ PUBACK để phát hiện ACL deny. Không được
        # chờ trong callback on_message vì callback chạy trên luồng mạng của
        # paho; chờ PUBACK tại đó sẽ làm luồng mạng không đọc được PUBACK.
        self._command_queue: queue.Queue[Any] = queue.Queue()
        self._command_worker: Optional[threading.Thread] = None

    def _gateway_status_envelope(self, status: str) -> dict[str, Any]:
        """Tạo envelope status cấp gateway."""
        return build_envelope(
            tenant_id=self.tenant_id,
            site_id=self.site_slug,
            gateway_id=self.gateway_id,
            source_site_id=self.source_site,
            device_type="gateway",
            device_id=self.gateway_id,
            category="status",
            data={"status": status},
            extra={"status": status},
        )

    def start(self) -> None:
        """Đăng ký LWT gateway rồi kết nối broker."""
        self._command_worker = threading.Thread(
            target=self._command_worker_loop,
            name=f"bridge-command-{self.gateway_id}",
            daemon=True,
        )
        self._command_worker.start()
        offline_payload = encode_envelope(
            self._gateway_status_envelope("offline")
        )
        headers, cid, ts_ms = build_headers(
            self.gateway_secret,
            self.status_topic,
            offline_payload,
        )
        will_props = make_will_properties(headers)
        self.client.set_will(
            self.status_topic,
            offline_payload,
            will_props,
            retain=self.config.northbound.retain_status,
        )
        self.logger.info(
            "Đăng ký LWT gateway topic=%s correlation_id=%s ts_ms=%s",
            self.status_topic,
            cid,
            ts_ms,
        )
        self.client.connect(
            keep_alive_sec=self.config.settings.keep_alive_sec,
            connect_properties=make_connect_properties(),
        )

    def _handle_connect(self) -> None:
        """Publish gateway online và subscribe hai chiều sau CONNACK."""
        online_payload = encode_envelope(
            self._gateway_status_envelope("online")
        )
        self._publish_on_topic(
            self.status_topic,
            online_payload,
            retain=self.config.northbound.retain_status,
        )
        for topic in (
            f"telemetry/{TOPIC_VERSION}/{self.source_site}/+/+",
            f"status/{TOPIC_VERSION}/{self.source_site}/+/+",
            f"alerts/{TOPIC_VERSION}/{self.source_site}/+/+",
            (
                f"commands/{TOPIC_VERSION}/{self.source_site}/+/+/dim/result"
            ),
            self.command_topic,
        ):
            self.client.subscribe(topic, qos=1)
        self.logger.info(
            "Gateway bridge sẵn sàng gateway=%s site=%s devices=%s",
            self.gateway_id,
            self.source_site,
            len(self.devices),
        )

    def _handle_disconnect(self) -> None:
        """Log mất kết nối; paho tự reconnect và LWT đã được broker phát."""
        self.logger.warning(
            "Gateway bridge mất kết nối gateway=%s; chờ paho reconnect",
            self.gateway_id,
        )

    def _publish_on_topic(
        self,
        topic: str,
        payload: str,
        retain: bool = False,
        correlation_id: Optional[str] = None,
        message_expiry_interval: Optional[int] = None,
        response_topic: Optional[str] = None,
        wait_for_ack: bool = False,
    ) -> bool:
        """Ký bằng khóa gateway và publish một payload đã serialize."""
        headers, cid, ts_ms = build_headers(
            self.gateway_secret,
            topic,
            payload,
            correlation_id=correlation_id,
        )
        props = make_publish_properties(
            headers,
            content_type=CONTENT_TYPE_JSON,
            message_expiry_interval=message_expiry_interval,
            correlation_data=cid.encode("utf-8"),
            response_topic=response_topic,
        )
        ok = self.client.publish(
            topic,
            payload,
            qos=1,
            retain=retain,
            properties=props,
            wait_for_ack=wait_for_ack,
        )
        self.logger.debug(
            "NORTHBOUND_TX topic=%s correlation_id=%s ts_ms=%s ok=%s",
            topic,
            cid,
            ts_ms,
            ok,
        )
        return ok

    def _publish_envelope(
        self,
        category: str,
        envelope: dict[str, Any],
        correlation_id: Optional[str] = None,
        retain: bool = False,
    ) -> bool:
        """Publish envelope canonical lên topic northbound."""
        topic = northbound_topic(
            self.tenant_id,
            self.site_slug,
            self.gateway_id,
            category,
        )
        return self._publish_on_topic(
            topic,
            encode_envelope(envelope),
            retain=retain,
            correlation_id=correlation_id,
        )

    def _handle_message(self, message: Any) -> None:
        """Phân luồng message northbound cmd và southbound telemetry/status."""
        topic = message.topic
        if topic == self.command_topic:
            self._command_queue.put(message)
            return

        try:
            parsed = parse_topic(topic)
        except ValueError as exc:
            self.logger.warning(
                "Bỏ qua southbound topic không hợp lệ topic=%s error=%s",
                topic,
                exc,
            )
            return

        if parsed.site_id != self.source_site:
            return

        key = (parsed.device_type, parsed.device_id)
        spec = self.devices.get(key)
        if spec is None:
            self.logger.warning(
                "Bỏ qua thiết bị không thuộc gateway topic=%s gateway=%s",
                topic,
                self.gateway_id,
            )
            return

        payload_bytes = bytes(message.payload)
        raw_props = getattr(message.properties, "UserProperty", None)
        enforce_ts = parsed.category != "status"
        try:
            cid, ts_ms, _ = verify_envelope(
                self.device_secrets[key],
                topic,
                payload_bytes,
                raw_props,
                replay_guard=(
                    self.device_guards[key] if enforce_ts else None
                ),
                enforce_timestamp=enforce_ts,
            )
        except HeaderError as exc:
            self._reject_southbound(spec, ALERT_HEADER_MISSING, "HIGH", str(exc))
            return
        except SignatureError as exc:
            self._reject_southbound(
                spec,
                ALERT_SIGNATURE_INVALID,
                "HIGH",
                str(exc),
            )
            return
        except ReplayError as exc:
            self._reject_southbound(spec, ALERT_REPLAY_DETECTED, "HIGH", str(exc))
            return

        try:
            self._forward_southbound(parsed, spec, payload_bytes, cid, ts_ms)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            self.logger.warning(
                "Không map được payload southbound topic=%s device=%s error=%s",
                topic,
                spec.device_id,
                exc,
            )

    def _command_worker_loop(self) -> None:
        """Xử lý command ngoài luồng mạng để publish có thể chờ PUBACK."""
        while True:
            message = self._command_queue.get()
            try:
                if message is None:
                    return
                self._handle_command(message)
            except Exception:  # pragma: no cover - lỗi một command không dừng worker
                self.logger.exception("Lỗi xử lý command northbound")
            finally:
                self._command_queue.task_done()

    def _forward_southbound(
        self,
        parsed: Any,
        spec: DeviceSpec,
        payload_bytes: bytes,
        cid: str,
        ts_ms: int,
    ) -> None:
        """Map một message southbound sang category northbound tương ứng."""
        if parsed.category == "status":
            status = payload_bytes.decode("utf-8", errors="replace")
            envelope = build_envelope(
                tenant_id=self.tenant_id,
                site_id=self.site_slug,
                gateway_id=self.gateway_id,
                source_site_id=self.source_site,
                device_type=spec.device_type,
                device_id=spec.device_id,
                category="status",
                data=status,
                extra={"status": status},
            )
            self._publish_envelope("status", envelope)
            self.logger.info(
                "STATUS_FWD device=%s status=%s gateway=%s",
                spec.device_id,
                status,
                self.gateway_id,
            )
            return

        data = json.loads(payload_bytes.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("payload southbound phải là JSON object")

        if parsed.category == "telemetry":
            envelope = build_envelope(
                tenant_id=self.tenant_id,
                site_id=self.site_slug,
                gateway_id=self.gateway_id,
                source_site_id=self.source_site,
                device_type=spec.device_type,
                device_id=spec.device_id,
                category="telemetry",
                data=data,
                source_time=data.get("source_time"),
            )
            self._publish_envelope("telemetry", envelope)
            self.logger.info(
                "TELEMETRY_FWD device=%s seq=%s gateway=%s",
                spec.device_id,
                data.get("sequence"),
                self.gateway_id,
            )
            return

        if parsed.category == "command_result":
            status = normalize_ack_status(data.get("status"))
            envelope = build_envelope(
                tenant_id=self.tenant_id,
                site_id=self.site_slug,
                gateway_id=self.gateway_id,
                source_site_id=self.source_site,
                device_type=spec.device_type,
                device_id=spec.device_id,
                category="ack",
                data=data,
                source_time=data.get("device_time"),
                extra={
                    "command_id": data.get("command_id"),
                    "status": status,
                    "reason": data.get("reason"),
                    "observed_value": data.get("observed_value"),
                },
            )
            self._publish_envelope("ack", envelope, correlation_id=cid)
            self.logger.info(
                "ACK_FWD device=%s command_id=%s status=%s gateway=%s "
                "correlation_id=%s ts_ms=%s",
                spec.device_id,
                data.get("command_id"),
                status,
                self.gateway_id,
                cid,
                ts_ms,
            )
            return

        if parsed.category == "alerts":
            envelope = build_envelope(
                tenant_id=self.tenant_id,
                site_id=self.site_slug,
                gateway_id=self.gateway_id,
                source_site_id=self.source_site,
                device_type=spec.device_type,
                device_id=spec.device_id,
                category="alerts",
                data=data,
                extra={
                    "alert_code": data.get("alert_code"),
                    "severity": data.get("severity"),
                    "message": data.get("message"),
                    "related_correlation_id": data.get(
                        "related_correlation_id"
                    ),
                },
            )
            self._publish_envelope("alerts", envelope)
            self.logger.warning(
                "ALERT_FWD device=%s code=%s severity=%s gateway=%s",
                spec.device_id,
                data.get("alert_code"),
                data.get("severity"),
                self.gateway_id,
            )

    def _handle_command(self, message: Any) -> None:
        """Xác thực lệnh northbound, fan-out xuống đúng thiết bị southbound."""
        payload_bytes = bytes(message.payload)
        raw_props = getattr(message.properties, "UserProperty", None)
        try:
            cid, ts_ms, _ = verify_envelope(
                self.gateway_secret,
                message.topic,
                payload_bytes,
                raw_props,
                replay_guard=self.gateway_guard,
                enforce_timestamp=True,
            )
        except (HeaderError, SignatureError, ReplayError) as exc:
            self.logger.warning(
                "Từ chối lệnh northbound topic=%s gateway=%s error=%s",
                message.topic,
                self.gateway_id,
                exc,
            )
            return

        try:
            envelope = parse_envelope(payload_bytes)
            self._validate_northbound_identity(envelope)
            target = command_target(envelope)
        except (NorthboundPayloadError, ValueError) as exc:
            self.logger.warning(
                "Lệnh northbound sai envelope gateway=%s error=%s",
                self.gateway_id,
                exc,
            )
            return

        source_site, device_type, device_id = target
        if source_site != self.source_site:
            self.logger.warning(
                "Lệnh nhắm sai site target=%s/%s/%s gateway_site=%s",
                source_site,
                device_type,
                device_id,
                self.source_site,
            )
            return

        spec = self.devices.get((device_type, device_id))
        if spec is None:
            self.logger.warning(
                "Lệnh nhắm thiết bị không thuộc gateway target=%s/%s/%s",
                source_site,
                device_type,
                device_id,
            )
            self._publish_ack_reject(
                device_type,
                device_id,
                cid,
                "Target device is not registered on this gateway",
            )
            return

        body = envelope.get("data")
        if not isinstance(body, dict):
            body = {}
        action = str(envelope.get("action") or body.get("action") or "").upper()
        requested_value = envelope.get(
            "requested_value",
            envelope.get("value", body.get("requested_value", body.get("value"))),
        )
        command_id = str(
            envelope.get("command_id")
            or body.get("command_id")
            or cid
        )
        if not action:
            self._publish_ack_reject(
                device_type,
                device_id,
                cid,
                "Command action is missing",
                command_id=command_id,
            )
            return
        if action != "DIM":
            self._publish_ack_reject(
                device_type,
                device_id,
                cid,
                f"Unsupported command action: {action}",
                command_id=command_id,
            )
            return
        if requested_value is None:
            self._publish_ack_reject(
                device_type,
                device_id,
                cid,
                "Command requested_value is missing",
                command_id=command_id,
            )
            return

        try:
            expires_at = int(
                envelope.get("expires_at")
                or body.get("expires_at")
                or (time.time() + COMMAND_MESSAGE_EXPIRY_SEC)
            )
            issued_at = int(
                envelope.get("issued_at")
                or body.get("issued_at")
                or time.time()
            )
            priority = int(
                envelope.get("priority", body.get("priority", 1))
            )
        except (TypeError, ValueError):
            self._publish_ack_reject(
                device_type,
                device_id,
                cid,
                "Command metadata is invalid",
                command_id=command_id,
            )
            return
        if expires_at <= int(time.time()):
            self._publish_ack_reject(
                device_type,
                device_id,
                cid,
                "Command expired before fan-out",
                command_id=command_id,
            )
            return

        south_payload_obj = {
            "command_id": command_id,
            "actor": envelope.get("actor") or "GatewayBridge",
            "action": action,
            "requested_value": requested_value,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "priority": priority,
        }
        south_payload = json.dumps(
            south_payload_obj,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        south_topic = command_dim_topic(
            spec.site_id,
            spec.device_type,
            spec.device_id,
        )
        result_topic = command_result_topic(
            spec.site_id,
            spec.device_type,
            spec.device_id,
        )
        key = (spec.device_type, spec.device_id)
        headers, _, command_ts = build_headers(
            self.device_secrets[key],
            south_topic,
            south_payload,
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
            south_topic,
            south_payload,
            qos=1,
            retain=False,
            properties=props,
        )
        self.logger.info(
            "COMMAND_FWD gateway=%s device=%s action=%s value=%s "
            "topic=%s command_id=%s correlation_id=%s ts_ms=%s ok=%s",
            self.gateway_id,
            spec.device_id,
            action,
            requested_value,
            south_topic,
            command_id,
            cid,
            ts_ms,
            ok,
        )
        if not ok:
            self._publish_ack_reject(
                device_type,
                device_id,
                cid,
                "Gateway could not publish command southbound",
                command_id=command_id,
            )
        else:
            self.logger.debug("Command signed southbound ts_ms=%s", command_ts)

    def _validate_northbound_identity(self, envelope: dict[str, Any]) -> None:
        """Bảo đảm envelope không mạo danh tenant/site/gateway khác."""
        expected = (self.tenant_id, self.site_slug, self.gateway_id)
        actual = (
            str(envelope.get("tenant_id")),
            str(envelope.get("site_id")),
            str(envelope.get("gateway_id")),
        )
        if actual != expected:
            raise NorthboundPayloadError(
                f"Envelope identity {actual} không khớp {expected}"
            )

    def _publish_ack_reject(
        self,
        device_type: str,
        device_id: str,
        correlation_id: str,
        reason: str,
        command_id: Optional[str] = None,
    ) -> None:
        """Phát ack rejected để Cloud không treo lệnh khi bridge từ chối."""
        try:
            validate_device_type(device_type)
        except ValueError:
            self.logger.warning(
                "Không phát được ack rejected vì device_type lạ: %s",
                device_type,
            )
            return
        ack_id = command_id or correlation_id
        data = {
            "command_id": ack_id,
            "asset_id": device_id,
            "device_id": device_id,
            "status": "rejected",
            "reason": reason,
            "observed_value": None,
            "evidence_source": "GATEWAY_BRIDGE",
        }
        envelope = build_envelope(
            tenant_id=self.tenant_id,
            site_id=self.site_slug,
            gateway_id=self.gateway_id,
            source_site_id=self.source_site,
            device_type=device_type,
            device_id=device_id,
            category="ack",
            data=data,
            extra={
                "command_id": ack_id,
                "status": "rejected",
                "reason": reason,
            },
        )
        self._publish_envelope("ack", envelope, correlation_id=correlation_id)
        self.logger.warning(
            "ACK_REJECT gateway=%s device=%s command_id=%s correlation_id=%s",
            self.gateway_id,
            device_id,
            ack_id,
            correlation_id,
        )

    def _reject_southbound(
        self,
        spec: DeviceSpec,
        alert_code: str,
        severity: str,
        message: str,
    ) -> None:
        """Chuyển lỗi xác thực southbound thành alert northbound."""
        data = {
            "alert_code": alert_code,
            "severity": severity,
            "message": message,
            "device_id": spec.device_id,
            "ts_ms": now_ms(),
        }
        envelope = build_envelope(
            tenant_id=self.tenant_id,
            site_id=self.site_slug,
            gateway_id=self.gateway_id,
            source_site_id=self.source_site,
            device_type=spec.device_type,
            device_id=spec.device_id,
            category="alerts",
            data=data,
            extra={
                "alert_code": alert_code,
                "severity": severity,
                "message": message,
            },
        )
        self._publish_envelope("alerts", envelope)
        self.logger.warning(
            "REJECT southbound gateway=%s device=%s code=%s reason=%s",
            self.gateway_id,
            spec.device_id,
            alert_code,
            message,
        )

    def stop(self, graceful: bool = True) -> None:
        """Publish offline rồi ngắt kết nối nếu dừng chủ động."""
        if self._command_worker is not None:
            self._command_queue.put(None)
            self._command_worker.join(timeout=10)
            self._command_worker = None
        if graceful and self.client.is_connected:
            offline_payload = encode_envelope(
                self._gateway_status_envelope("offline")
            )
            self._publish_on_topic(
                self.status_topic,
                offline_payload,
                retain=self.config.northbound.retain_status,
                wait_for_ack=True,
            )
        self.client.stop()
        self.logger.info(
            "Đã dừng gateway bridge gateway=%s site=%s",
            self.gateway_id,
            self.source_site,
        )


class GatewayBridge:
    """Tập hợp nhiều GatewayLink, mỗi gateway một kết nối/LWT riêng."""

    def __init__(
        self,
        config: SimulatorConfig,
        logger: logging.Logger,
        source_sites: Optional[Sequence[str]] = None,
        gateway_override: Optional[str] = None,
    ) -> None:
        sites = list(source_sites or sorted({d.site_id for d in config.devices}))
        if gateway_override and len(sites) != 1:
            raise ConfigError(
                "--gateway chỉ dùng khi chọn đúng một --site"
            )
        self.links = [
            GatewayLink(
                config,
                site,
                gateway_override or config.gateway_for_site(site),
                logger.getChild(f"{site}"),
            )
            for site in sites
        ]

    def start(self) -> int:
        """Kết nối mọi gateway; trả về số kết nối thành công."""
        started = 0
        for link in self.links:
            try:
                link.start()
                started += 1
            except (MqttConnectionError, OSError) as exc:
                link.logger.error(
                    "Không kết nối được broker gateway=%s: %s",
                    link.gateway_id,
                    exc,
                )
        return started

    def stop(self, graceful: bool = True) -> None:
        """Dừng mọi gateway link."""
        for link in self.links:
            try:
                link.stop(graceful=graceful)
            except Exception:  # pragma: no cover - lỗi một link không chặn link khác
                link.logger.exception(
                    "Lỗi dừng gateway=%s",
                    link.gateway_id,
                )


def crash_after_delay(delay_sec: float, logger: logging.Logger) -> None:
    """Thoát tiến trình không gửi DISCONNECT để broker phát LWT gateway."""
    time.sleep(delay_sec)
    logger.critical(
        "CRASH MODE: thoát không DISCONNECT sau %.1fs để kiểm thử LWT",
        delay_sec,
    )
    os._exit(1)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Hàm main của gateway bridge."""
    args = parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"[CONFIG ERROR] {exc}", file=sys.stderr)
        return 2

    configure_logging(args.log_level or config.settings.log_level)
    logger = logging.getLogger(LOGGER_NAME)

    known_sites = sorted({d.site_id for d in config.devices})
    source_sites: Sequence[str] = known_sites
    if args.site:
        if args.site not in known_sites:
            logger.error(
                "Không tìm thấy site=%s trong config (có: %s)",
                args.site,
                ", ".join(known_sites),
            )
            return 2
        source_sites = [args.site]

    try:
        bridge = GatewayBridge(
            config,
            logger,
            source_sites=source_sites,
            gateway_override=args.gateway,
        )
    except ConfigError as exc:
        logger.error("%s", exc)
        return 2

    started = bridge.start()
    if not started:
        logger.error("Không có gateway nào kết nối được broker")
        return 1
    logger.info("Đã kết nối %s/%s gateway", started, len(bridge.links))

    if args.crash_after is not None:
        if args.crash_after <= 0:
            logger.error("--crash-after phải > 0")
            bridge.stop(graceful=True)
            return 2
        logger.warning(
            "CRASH MODE bật: thoát không DISCONNECT sau %.1fs",
            args.crash_after,
        )
        threading.Thread(
            target=crash_after_delay,
            args=(args.crash_after, logger),
            name="gateway-crash-timer",
            daemon=True,
        ).start()

    try:
        if args.run_seconds is not None:
            if args.run_seconds <= 0:
                logger.error("--run-seconds phải > 0")
                return 2
            time.sleep(args.run_seconds)
        else:
            while True:
                time.sleep(1.0)
    except KeyboardInterrupt:
        logger.info("Nhận Ctrl+C, dừng gateway bridge...")
    finally:
        bridge.stop(graceful=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
