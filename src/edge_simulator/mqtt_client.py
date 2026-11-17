"""Bọc paho-mqtt 2.x thành client MQTT 5 dùng chung cho simulator/mock cloud.

Vị trí trong luồng: Simulator -> Broker -> Cloud. Module này chịu trách nhiệm
CONNECT (Keep Alive, LWT, MQTT 5 Properties), publish/subscribe và callback.
Logic nghiệp vụ (telemetry, dim) nằm ở simulator_device.py.

Tại sao Keep Alive mặc định 15s: broker coi client mất kết nối sau khoảng
1.5 x Keep Alive (22.5s), vẫn còn biên an toàn so với yêu cầu phát hiện
offline trong 30s. Xem docs/specifications/MQTT5_COMMUNICATION_PROTOCOL.md.
"""

from __future__ import annotations

import collections
import logging
import ssl
import threading
from typing import Callable, Optional

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from paho.mqtt.properties import Properties

from .config import BrokerConfig

MessageCallback = Callable[[mqtt.MQTTMessage], None]
ConnectCallback = Callable[[], None]
DisconnectCallback = Callable[[], None]


def _reason_value(reason_code: object) -> int:
    """Chuẩn hóa ReasonCode/int của paho về số nguyên."""
    if reason_code is None:
        return 0
    return int(getattr(reason_code, "value", reason_code))


class MqttConnectionError(RuntimeError):
    """Không kết nối được broker trong thời gian chờ."""


class Mqtt5Client:
    """Client MQTT 5 tối giản, có LWT và callback rõ ràng.

    Mỗi thiết bị ngoại vi phải có một client riêng vì LWT/status/client_id gắn
    với từng kết nối TCP. Dùng chung một client cho nhiều thiết bị sẽ không
    thể phát hiện offline độc lập.
    """

    def __init__(
        self,
        broker: BrokerConfig,
        client_id: str,
        logger: logging.Logger,
    ) -> None:
        self.broker = broker
        self.logger = logger
        self.client_id = client_id
        self._connected = threading.Event()
        self._on_connect: Optional[ConnectCallback] = None
        self._on_disconnect: Optional[DisconnectCallback] = None
        self._on_message: Optional[MessageCallback] = None
        self._stopping = False
        self._keep_alive_sec = 0

        # MQTT 5 trả reason code trong PUBACK/SUBACK. Paho không đưa các mã
        # này vào MQTTMessageInfo, nên phải giữ lại để publish() biết ACL có
        # từ chối hay không thay vì coi mọi lần gửi là thành công.
        self._ack_lock = threading.Lock()
        self._ack_events: dict[int, threading.Event] = {}
        self._ack_reasons: dict[int, int] = {}
        self._ack_order: collections.deque[int] = collections.deque()
        self._subscribe_topics: dict[int, list[str]] = {}

        self._client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=client_id,
            protocol=mqtt.MQTTv5,
        )
        self._client.on_connect = self._handle_connect
        self._client.on_disconnect = self._handle_disconnect
        self._client.on_message = self._handle_message
        self._client.on_publish = self._handle_publish
        self._client.on_subscribe = self._handle_subscribe
        # Tự kết nối lại khi mạng chập chờn; LWT của kết nối cũ đã được broker
        # phát, kết nối mới sẽ publish lại trạng thái online retained.
        self._client.reconnect_delay_set(min_delay=1, max_delay=30)

        if broker.username:
            self._client.username_pw_set(broker.username, broker.password or None)
        if broker.use_tls:
            self._client.tls_set(
                ca_certs=broker.ca_cert,
                certfile=broker.client_cert,
                keyfile=broker.client_key,
                cert_reqs=ssl.CERT_REQUIRED,
            )
            if broker.tls_insecure:
                self.logger.warning(
                    "TLS hostname verification đang tắt; chỉ dùng cho lab"
                )
                self._client.tls_insecure_set(True)

    @property
    def is_connected(self) -> bool:
        """True nếu callback on_connect đã thành công và chưa disconnect."""
        return self._connected.is_set()

    def set_callbacks(
        self,
        on_connect: Optional[ConnectCallback] = None,
        on_message: Optional[MessageCallback] = None,
        on_disconnect: Optional[DisconnectCallback] = None,
    ) -> None:
        """Gắn callback nghiệp vụ; callback được gọi trong luồng mạng của paho."""
        self._on_connect = on_connect
        self._on_message = on_message
        self._on_disconnect = on_disconnect

    def set_will(
        self,
        topic: str,
        payload: bytes | str,
        properties: Properties,
        retain: bool = True,
    ) -> None:
        """Cấu hình LWT: QoS 1, Will Delay Interval = 0.

        retain=True phù hợp broker cho phép retained status. Northbound có
        thể đặt retain=False khi broker Tech Lead cấu hình
        `retain_available false`; khi đó LWT vẫn được giao cho subscriber
        đang kết nối. QoS 1 để giảm khả năng mất cảnh báo offline.
        """
        self._client.will_set(
            topic,
            payload=payload,
            qos=1,
            retain=retain,
            properties=properties,
        )

    def connect(
        self,
        keep_alive_sec: int,
        connect_properties: Properties,
        timeout_sec: float = 15.0,
    ) -> None:
        """Kết nối broker và chờ on_connect.

        Ngoại lệ:
            MqttConnectionError: Nếu lỗi TCP/MQTT hoặc quá thời gian chờ.
        """
        self._keep_alive_sec = keep_alive_sec
        try:
            self._client.connect(
                self.broker.host,
                self.broker.port,
                keepalive=keep_alive_sec,
                clean_start=True,
                properties=connect_properties,
            )
        except OSError as exc:
            raise MqttConnectionError(
                f"Không kết nối được {self.broker.host}:{self.broker.port}: {exc}"
            ) from exc

        self._client.loop_start()
        if not self._connected.wait(timeout_sec):
            self._client.loop_stop()
            raise MqttConnectionError(
                f"Hết thời gian chờ CONNACK từ {self.broker.host}:{self.broker.port}"
            )

    def wait_connected(self, timeout_sec: float = 10.0) -> bool:
        """Chờ tới khi kết nối sẵn sàng (dùng sau khi mất mạng tạm thời)."""
        return self._connected.wait(timeout_sec)

    def subscribe(self, topic: str, qos: int = 1) -> None:
        """Subscribe một topic với QoS cho trước."""
        result, mid = self._client.subscribe(topic, qos=qos)
        if result != mqtt.MQTT_ERR_SUCCESS:
            self.logger.error(
                "Subscribe thất bại topic=%s rc=%s mid=%s",
                topic,
                result,
                mid,
            )
            return
        self._subscribe_topics[mid] = [topic]
        self.logger.info("Đã subscribe topic=%s qos=%s mid=%s", topic, qos, mid)

    def publish(
        self,
        topic: str,
        payload: bytes | str,
        qos: int,
        retain: bool,
        properties: Properties,
        wait_for_ack: bool = True,
        wait_timeout_sec: float = 5.0,
    ) -> bool:
        """Publish một message.

        Tham số:
            wait_for_ack: True sẽ chờ PUBACK (QoS 1) trước khi trả về. Với
                telemetry/status tần suất cao, đặt False để không chặn luồng
                gọi; paho vẫn gửi và xử lý ack trong luồng mạng riêng.
            wait_timeout_sec: Thời gian chờ tối đa khi wait_for_ack=True.

        Trả về:
            True nếu message đã được đưa vào hàng đợi gửi (và ack nếu có chờ).
        """
        info = self._client.publish(
            topic,
            payload=payload,
            qos=qos,
            retain=retain,
            properties=properties,
        )
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            self.logger.error("Publish thất bại topic=%s rc=%s", topic, info.rc)
            return False
        if not wait_for_ack:
            return True
        if qos == 0:
            try:
                info.wait_for_publish(timeout=wait_timeout_sec)
            except (ValueError, RuntimeError) as exc:
                self.logger.error("Publish chưa hoàn tất topic=%s: %s", topic, exc)
                return False
            return True

        ack_event = threading.Event()
        with self._ack_lock:
            self._ack_events[info.mid] = ack_event
            early_reason = self._ack_reasons.pop(info.mid, None)
            if early_reason is not None:
                ack_event.set()
        if not ack_event.wait(wait_timeout_sec):
            with self._ack_lock:
                self._ack_events.pop(info.mid, None)
            self.logger.error(
                "Publish timeout chờ PUBACK topic=%s mid=%s",
                topic,
                info.mid,
            )
            return False
        with self._ack_lock:
            reason = self._ack_reasons.pop(info.mid, None)
            self._ack_events.pop(info.mid, None)
        if reason is None:
            self.logger.error(
                "Publish không nhận được PUBACK topic=%s mid=%s",
                topic,
                info.mid,
            )
            return False
        if reason >= 0x80:
            self.logger.error(
                "PUBACK từ chối topic=%s mid=%s reason=%s",
                topic,
                info.mid,
                reason,
            )
            return False
        return True

    def stop(self) -> None:
        """Ngắt kết nối chủ động (gửi DISCONNECT) và dừng luồng mạng."""
        if self._stopping:
            return
        self._stopping = True
        try:
            if self.is_connected:
                self._client.disconnect()
        finally:
            self._client.loop_stop()
            self._connected.clear()

    def _handle_publish(
        self,
        client: mqtt.Client,
        userdata: object,
        mid: int,
        reason_code: mqtt.ReasonCode,
        properties: Optional[Properties],
    ) -> None:
        """Ghi nhận PUBACK/PUBCOMP và đánh thức publish() đang chờ."""
        reason = _reason_value(reason_code)
        with self._ack_lock:
            self._ack_reasons[mid] = reason
            self._ack_order.append(mid)
            while len(self._ack_order) > 512:
                stale_mid = self._ack_order.popleft()
                if stale_mid in self._ack_events:
                    # Còn publish đang chờ; giữ reason lại cho waiter.
                    self._ack_order.append(stale_mid)
                    break
                self._ack_reasons.pop(stale_mid, None)
            event = self._ack_events.get(mid)
            if event is not None:
                event.set()
        if reason >= 0x80:
            self.logger.error(
                "PUBACK/PUBCOMP từ chối mid=%s reason=%s", mid, reason
            )
        else:
            self.logger.debug("PUBACK/PUBCOMP mid=%s reason=%s", mid, reason)

    def _handle_subscribe(
        self,
        client: mqtt.Client,
        userdata: object,
        mid: int,
        reason_code_list: list[mqtt.ReasonCode],
        properties: Optional[Properties],
    ) -> None:
        """Log SUBACK reason code để phát hiện ACL từ chối subscribe."""
        topics = self._subscribe_topics.pop(mid, [])
        codes = (
            reason_code_list
            if isinstance(reason_code_list, list)
            else [reason_code_list]
        )
        for topic, reason_code in zip(topics, codes):
            reason = _reason_value(reason_code)
            if reason >= 0x80:
                self.logger.error(
                    "SUBACK từ chối topic=%s mid=%s reason=%s",
                    topic,
                    mid,
                    reason,
                )
            else:
                self.logger.info(
                    "SUBACK chấp nhận topic=%s mid=%s qos=%s",
                    topic,
                    mid,
                    reason,
                )

    def _handle_connect(
        self,
        client: mqtt.Client,
        userdata: object,
        flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: Optional[Properties],
    ) -> None:
        """Nhận CONNACK; chỉ đánh dấu connected khi thành công."""
        if reason_code.is_failure:
            self.logger.error(
                "CONNACK thất bại client_id=%s reason=%s",
                self.client_id,
                reason_code,
            )
            self._connected.clear()
            return

        self._connected.set()
        self.logger.info(
            "Đã kết nối MQTT 5 broker=%s:%s client_id=%s keepalive=%ss",
            self.broker.host,
            self.broker.port,
            self.client_id,
            self._keep_alive_sec,
        )
        if self._on_connect is not None:
            try:
                self._on_connect()
            except Exception:  # pragma: no cover - lỗi callback phải được log
                self.logger.exception(
                    "Lỗi trong on_connect client_id=%s",
                    self.client_id,
                )

    def _handle_disconnect(
        self,
        client: mqtt.Client,
        userdata: object,
        disconnect_flags: mqtt.DisconnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: Optional[Properties],
    ) -> None:
        """Nhận DISCONNECT; paho sẽ tự reconnect nếu loop vẫn chạy."""
        self._connected.clear()
        if self._stopping:
            self.logger.info("Đã ngắt kết nối chủ động client_id=%s", self.client_id)
            return
        self.logger.warning(
            "Mất kết nối client_id=%s reason=%s; paho sẽ tự thử lại",
            self.client_id,
            reason_code,
        )
        if self._on_disconnect is not None:
            try:
                self._on_disconnect()
            except Exception:  # pragma: no cover
                self.logger.exception(
                    "Lỗi trong on_disconnect client_id=%s",
                    self.client_id,
                )

    def _handle_message(
        self,
        client: mqtt.Client,
        userdata: object,
        message: mqtt.MQTTMessage,
    ) -> None:
        """Chuyển message về callback nghiệp vụ, không để lỗi làm chết loop."""
        if self._on_message is None:
            return
        try:
            self._on_message(message)
        except Exception:  # pragma: no cover
            self.logger.exception(
                "Lỗi xử lý message topic=%s client_id=%s",
                message.topic,
                self.client_id,
            )
