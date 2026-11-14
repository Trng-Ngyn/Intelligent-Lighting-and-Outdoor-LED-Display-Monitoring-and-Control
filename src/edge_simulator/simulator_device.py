"""Mô phỏng một thiết bị ngoại vi (đèn/LED/gateway) nói MQTT 5.

Vị trí trong luồng: Simulator -> Broker -> Cloud. Mỗi instance đại diện một
kết nối MQTT riêng (client_id, LWT, status riêng), publish telemetry định kỳ
và xử lý lệnh dim nhận từ Cloud.

Payload telemetry/command/result giữ nguyên schema hiện có. Phần mới chỉ là
topic phân tầng v1 và bộ User Properties correlation_id/ts_ms/signature.

Xem docs/specifications/MQTT5_COMMUNICATION_PROTOCOL.md và
src/edge_simulator/README.md.
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
from typing import Any, Optional

from iot_protocol.headers import (
    ALERT_COMMAND_EXPIRED,
    ALERT_HEADER_MISSING,
    ALERT_INVALID_PAYLOAD,
    ALERT_REPLAY_DETECTED,
    ALERT_SIGNATURE_INVALID,
    ALERT_UNSUPPORTED_ACTION,
    HeaderError,
    build_headers,
    verify_envelope,
)
from iot_protocol.mqtt5 import (
    CONTENT_TYPE_JSON,
    CONTENT_TYPE_TEXT,
    make_connect_properties,
    make_publish_properties,
    make_will_properties,
)
from iot_protocol.signing import (
    ReplayError,
    ReplayGuard,
    SignatureError,
    derive_device_key,
    now_ms,
)
from iot_protocol.topics import (
    alerts_topic,
    command_dim_topic,
    command_result_topic,
    status_topic,
    telemetry_topic,
)

from .config import DeviceSpec, SimulatorConfig
from .mqtt_client import Mqtt5Client

STATUS_ONLINE = "online"
STATUS_OFFLINE = "offline"
MAX_BRIGHTNESS = 100
MAX_TELEMETRY_SLEEP_SEC = 3600.0


class SimulatorDevice:
    """Trạng thái và hành vi của một thiết bị ngoại vi giả lập."""

    def __init__(
        self,
        spec: DeviceSpec,
        config: SimulatorConfig,
        logger: logging.Logger,
    ) -> None:
        self.spec = spec
        self.config = config
        self.logger = logger
        self.secret = derive_device_key(
            config.security.signing_secret,
            spec.site_id,
            spec.device_type,
            spec.device_id,
        )
        self.replay_guard = ReplayGuard(
            window_ms=config.settings.replay_window_ms
        )

        self.telemetry_topic = telemetry_topic(
            spec.site_id, spec.device_type, spec.device_id
        )
        self.command_topic = command_dim_topic(
            spec.site_id, spec.device_type, spec.device_id
        )
        self.result_topic = command_result_topic(
            spec.site_id, spec.device_type, spec.device_id
        )
        self.status_topic = status_topic(
            spec.site_id, spec.device_type, spec.device_id
        )
        self.alerts_topic = alerts_topic(
            spec.site_id, spec.device_type, spec.device_id
        )

        client_id = (
            f"{config.broker.client_id_prefix}-"
            f"{spec.site_id}-{spec.device_type}-{spec.device_id}"
        )
        self.client = Mqtt5Client(config.broker, client_id, logger)
        self.client.set_callbacks(
            on_connect=self._handle_connect,
            on_message=self._handle_message,
            on_disconnect=self._handle_disconnect,
        )

        self.brightness = spec.initial_brightness
        self.relay_state = True
        self.voltage = 220.0
        self.temperature = 35.0
        self.cumulative_wh = 100.0 + random.uniform(10.0, 50.0)
        self.sequence = 0
        self._last_status = None

    def start(self) -> None:
        """Thiết lập LWT rồi kết nối broker.

        LWT được đăng ký trước connect vì broker chỉ nhận Will trong gói
        CONNECT. Chuỗi ký của Will dùng ts_ms tại thời điểm connect; Cloud
        được phép bỏ qua cửa sổ replay cho status (xem tài liệu đặc tả).

        Ngoại lệ:
            MqttConnectionError: Nếu không kết nối được broker.
        """
        will_payload = STATUS_OFFLINE
        will_headers, will_cid, will_ts = build_headers(
            self.secret,
            self.status_topic,
            will_payload,
        )
        will_props = make_will_properties(
            will_headers,
            content_type=CONTENT_TYPE_TEXT,
        )
        self.client.set_will(self.status_topic, will_payload, will_props)
        self.logger.info(
            "Đăng ký LWT topic=%s payload=%s correlation_id=%s ts_ms=%s",
            self.status_topic,
            will_payload,
            will_cid,
            will_ts,
        )

        self.client.connect(
            keep_alive_sec=self.config.settings.keep_alive_sec,
            connect_properties=make_connect_properties(),
        )

    def _handle_connect(self) -> None:
        """Publish online retained và subscribe lệnh sau mỗi lần CONNACK."""
        self._publish_status(STATUS_ONLINE, wait_for_ack=False)
        self.client.subscribe(self.command_topic, qos=1)
        self.logger.info(
            "Thiết bị sẵn sàng device=%s/%s/%s",
            self.spec.site_id,
            self.spec.device_type,
            self.spec.device_id,
        )

    def _handle_disconnect(self) -> None:
        """Xóa trạng thái đã publish để lần reconnect sau publish lại online."""
        self._last_status = None

    def _publish_status(self, status: str, wait_for_ack: bool = True) -> None:
        """Publish status online/offline retained bằng MQTT 5.

        Tại sao retain=true: Cloud subscribe muộn vẫn nhận được trạng thái mới
        nhất. QoS 1 để giảm khả năng mất bản tin offline khi đường truyền yếu.
        """
        headers, cid, ts_ms = build_headers(
            self.secret,
            self.status_topic,
            status,
        )
        props = make_publish_properties(
            headers,
            content_type=CONTENT_TYPE_TEXT,
            correlation_data=cid.encode("utf-8"),
        )
        ok = self.client.publish(
            self.status_topic,
            status,
            qos=1,
            retain=True,
            properties=props,
            wait_for_ack=wait_for_ack,
        )
        self._last_status = status
        self.logger.info(
            "STATUS %s topic=%s correlation_id=%s ts_ms=%s ok=%s",
            status,
            self.status_topic,
            cid,
            ts_ms,
            ok,
        )

    def publish_telemetry(self) -> None:
        """Tạo và publish một bản tin telemetry theo schema Annex C hiện có."""
        if not self.client.is_connected:
            self.logger.warning(
                "Bỏ qua telemetry vì chưa kết nối device=%s",
                self.spec.device_id,
            )
            return

        self.sequence += 1
        ambient_lux = random.uniform(20.0, 450.0)
        voltage = self.voltage + random.uniform(-1.5, 1.5)
        if self.relay_state:
            power_w = (
                (self.brightness / MAX_BRIGHTNESS)
                * 100.0
                * random.uniform(0.96, 1.02)
            )
        else:
            power_w = 0.0
        current_a = power_w / voltage if voltage > 0 else 0.0
        interval_hours = self.config.settings.telemetry_interval_sec / 3600.0
        self.cumulative_wh += power_w * interval_hours
        temperature = 32.0 + (self.brightness * 0.3) + random.uniform(-0.5, 0.5)

        payload_obj = {
            "schema_version": "1.0.0",
            "message_id": (
                f"MSG_{now_ms()}_{self.spec.device_id}_{self.sequence}"
            ),
            "asset_id": self.spec.device_id,
            "sequence": self.sequence,
            "source_time": int(time.time()),
            "metrics": {
                "power_w": round(power_w, 2),
                "energy_wh": round(self.cumulative_wh, 2),
                "voltage_v": round(voltage, 1),
                "current_a": round(current_a, 3),
                "power_factor": 0.95,
                "temperature_c": round(temperature, 1),
                "ambient_lux": round(ambient_lux, 1),
            },
            "brightness_pct": self.brightness,
            "relay_state": self.relay_state,
            "quality": "GOOD",
        }
        payload = json.dumps(
            payload_obj,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        headers, cid, ts_ms = build_headers(
            self.secret,
            self.telemetry_topic,
            payload,
        )
        props = make_publish_properties(
            headers,
            content_type=CONTENT_TYPE_JSON,
            correlation_data=cid.encode("utf-8"),
        )
        ok = self.client.publish(
            self.telemetry_topic,
            payload,
            qos=1,
            retain=False,
            properties=props,
            wait_for_ack=False,
        )
        self.logger.info(
            "TELEMETRY topic=%s correlation_id=%s ts_ms=%s seq=%s ok=%s",
            self.telemetry_topic,
            cid,
            ts_ms,
            self.sequence,
            ok,
        )

    def _handle_message(self, message: Any) -> None:
        """Xử lý lệnh dim nhận từ broker.

        Thứ tự kiểm tra: topic -> header -> chữ ký -> chống replay -> payload
        -> hạn lệnh. Bản tin sai ở bất kỳ bước nào đều bị từ chối và phát alert.
        """
        if message.topic != self.command_topic:
            self.logger.warning(
                "Bỏ qua message ngoài topic lệnh topic=%s expected=%s",
                message.topic,
                self.command_topic,
            )
            return

        payload_bytes = bytes(message.payload)
        payload_text = payload_bytes.decode("utf-8", errors="replace")
        raw_props = getattr(message.properties, "UserProperty", None)
        cid: Optional[str] = None
        ts_ms: Optional[int] = None

        try:
            cid, ts_ms, _ = verify_envelope(
                self.secret,
                message.topic,
                payload_bytes,
                raw_props,
                replay_guard=self.replay_guard,
                enforce_timestamp=True,
            )
            self._check_correlation_data(message, cid)

            command = json.loads(payload_text)
            if not isinstance(command, dict):
                raise ValueError("payload lệnh phải là JSON object")
        except HeaderError as exc:
            self.logger.warning(
                "Từ chối lệnh thiếu/sai header topic=%s error=%s",
                message.topic,
                exc,
            )
            self._publish_alert(
                ALERT_HEADER_MISSING,
                "HIGH",
                str(exc),
                related_correlation_id=cid,
            )
            return
        except SignatureError as exc:
            self.logger.warning(
                "Từ chối lệnh sai chữ ký topic=%s correlation_id=%s error=%s",
                message.topic,
                cid,
                exc,
            )
            self._publish_alert(
                ALERT_SIGNATURE_INVALID,
                "HIGH",
                str(exc),
                related_correlation_id=cid,
            )
            return
        except ReplayError as exc:
            self.logger.warning(
                "Từ chối lệnh replay topic=%s correlation_id=%s error=%s",
                message.topic,
                cid,
                exc,
            )
            self._publish_alert(
                ALERT_REPLAY_DETECTED,
                "HIGH",
                str(exc),
                related_correlation_id=cid,
            )
            return
        except (json.JSONDecodeError, ValueError) as exc:
            self.logger.warning(
                "Từ chối lệnh sai payload topic=%s correlation_id=%s error=%s",
                message.topic,
                cid,
                exc,
            )
            self._publish_alert(
                ALERT_INVALID_PAYLOAD,
                "MEDIUM",
                str(exc),
                related_correlation_id=cid,
            )
            return

        cmd_id = str(command.get("command_id") or cid)
        action = str(command.get("action", "NONE")).upper()
        requested_value = command.get("requested_value", 0)
        expires_at = int(command.get("expires_at", 0) or 0)

        self.logger.info(
            "COMMAND RX topic=%s correlation_id=%s command_id=%s ts_ms=%s "
            "action=%s value=%s",
            message.topic,
            cid,
            cmd_id,
            ts_ms,
            action,
            requested_value,
        )

        if expires_at > 0 and int(time.time()) > expires_at:
            self.logger.warning(
                "Lệnh hết hạn command_id=%s correlation_id=%s expires_at=%s",
                cmd_id,
                cid,
                expires_at,
            )
            self._publish_result(
                cid,
                cmd_id,
                "EXPIRED",
                "Command arrived after expiration timestamp",
                self.brightness,
            )
            self._publish_alert(
                ALERT_COMMAND_EXPIRED,
                "MEDIUM",
                f"Lệnh {cmd_id} hết hạn",
                related_correlation_id=cid,
            )
            return

        if action == "DIM":
            try:
                value = int(requested_value)
            except (TypeError, ValueError):
                value = -1
            if value < 0 or value > MAX_BRIGHTNESS:
                self._publish_result(
                    cid,
                    cmd_id,
                    "REJECTED",
                    "Brightness out of range [0-100]",
                    self.brightness,
                )
                self._publish_alert(
                    ALERT_UNSUPPORTED_ACTION,
                    "MEDIUM",
                    f"Giá trị dim không hợp lệ: {requested_value!r}",
                    related_correlation_id=cid,
                )
                return
            self.brightness = value
            self.logger.info(
                "Đã dim device=%s brightness=%s correlation_id=%s",
                self.spec.device_id,
                self.brightness,
                cid,
            )
            self._publish_result(
                cid,
                cmd_id,
                "EXECUTED",
                "Virtual driver updated state",
                self.brightness,
            )
            return

        if action == "SWITCH":
            self.relay_state = bool(requested_value)
            if not self.relay_state:
                self.brightness = 0
            self.logger.info(
                "Đã switch device=%s relay=%s brightness=%s correlation_id=%s",
                self.spec.device_id,
                self.relay_state,
                self.brightness,
                cid,
            )
            self._publish_result(
                cid,
                cmd_id,
                "EXECUTED",
                (
                    "Virtual relay turned ON"
                    if self.relay_state
                    else "Virtual relay turned OFF"
                ),
                self.brightness,
            )
            return

        self._publish_result(
            cid,
            cmd_id,
            "REJECTED",
            "Unsupported action type",
            self.brightness,
        )
        self._publish_alert(
            ALERT_UNSUPPORTED_ACTION,
            "MEDIUM",
            f"Action không hỗ trợ: {action}",
            related_correlation_id=cid,
        )

    def _check_correlation_data(self, message: Any, cid: str) -> None:
        """Đối chiếu Correlation Data chuẩn MQTT 5 với User Property.

        Nếu Cloud gửi kèm CorrelationData khác correlation_id, coi như header
        không nhất quán để tránh hai nguồn định danh mâu thuẫn.
        """
        correlation_data = getattr(message.properties, "CorrelationData", None)
        if correlation_data is None:
            return
        try:
            decoded = bytes(correlation_data).decode("utf-8")
        except (TypeError, UnicodeDecodeError) as exc:
            raise HeaderError("CorrelationData không phải UTF-8") from exc
        if decoded != cid:
            raise HeaderError(
                "CorrelationData không khớp correlation_id User Property"
            )

    def _publish_result(
        self,
        correlation_id: str,
        command_id: str,
        status: str,
        reason: str,
        observed_value: int,
    ) -> None:
        """Publish phản hồi lệnh với đúng correlation_id của lệnh gốc."""
        payload_obj = {
            "command_id": command_id,
            "asset_id": self.spec.device_id,
            "device_time": int(time.time()),
            "status": status,
            "reason": reason,
            "observed_value": observed_value,
            "evidence_source": "VIRTUAL_PWM_SENSOR",
        }
        payload = json.dumps(
            payload_obj,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        headers, _, ts_ms = build_headers(
            self.secret,
            self.result_topic,
            payload,
            correlation_id=correlation_id,
            ts_ms=now_ms(),
        )
        props = make_publish_properties(
            headers,
            content_type=CONTENT_TYPE_JSON,
            correlation_data=correlation_id.encode("utf-8"),
        )
        ok = self.client.publish(
            self.result_topic,
            payload,
            qos=1,
            retain=False,
            properties=props,
            wait_for_ack=False,
        )
        self.logger.info(
            "RESULT topic=%s correlation_id=%s ts_ms=%s status=%s ok=%s",
            self.result_topic,
            correlation_id,
            ts_ms,
            status,
            ok,
        )

    def _publish_alert(
        self,
        alert_code: str,
        severity: str,
        message: str,
        related_correlation_id: Optional[str] = None,
    ) -> None:
        """Phát alert bảo mật/vận hành lên topic alerts/v1/....

        Alert dùng correlation_id mới của chính nó; mã lệnh liên quan được giữ
        trong payload để Cloud truy vết mà không làm mất định danh của alert.
        """
        payload_obj = {
            "schema_version": "1.0.0",
            "alert_code": alert_code,
            "severity": severity,
            "message": message,
            "device_id": self.spec.device_id,
            "ts_ms": now_ms(),
        }
        if related_correlation_id:
            payload_obj["related_correlation_id"] = related_correlation_id
        payload = json.dumps(
            payload_obj,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        headers, cid, ts_ms = build_headers(
            self.secret,
            self.alerts_topic,
            payload,
        )
        props = make_publish_properties(
            headers,
            content_type=CONTENT_TYPE_JSON,
            correlation_data=cid.encode("utf-8"),
        )
        ok = self.client.publish(
            self.alerts_topic,
            payload,
            qos=1,
            retain=False,
            properties=props,
            wait_for_ack=False,
        )
        self.logger.warning(
            "ALERT topic=%s correlation_id=%s ts_ms=%s code=%s ok=%s",
            self.alerts_topic,
            cid,
            ts_ms,
            alert_code,
            ok,
        )

    def stop(self, graceful: bool = True) -> None:
        """Dừng thiết bị.

        Nếu graceful=True, publish offline retained trước khi gửi DISCONNECT.
        Nếu cần kiểm thử LWT, KHÔNG gọi hàm này mà dùng chế độ crash để tiến
        trình thoát mà không gửi DISCONNECT.
        """
        if graceful and self.client.is_connected:
            self._publish_status(STATUS_OFFLINE, wait_for_ack=True)
        self.client.stop()
        self.logger.info("Đã dừng thiết bị %s", self.spec.device_id)

    def crash_process(self) -> None:
        """Thoát tiến trình ngay lập tức, không gửi DISCONNECT.

        Dùng cho kịch bản kiểm thử LWT: broker chỉ biết thiết bị mất kết nối
        qua TCP/Keep Alive và phát Will message.
        """
        self.logger.critical(
            "CRASH MODE: thoát tiến trình không gửi DISCONNECT device=%s",
            self.spec.device_id,
        )
        os._exit(1)
