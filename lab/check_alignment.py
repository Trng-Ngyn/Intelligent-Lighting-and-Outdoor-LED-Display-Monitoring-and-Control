#!/usr/bin/env python3
"""Kiểm tra topic Annex C, retain policy và LWT trên listener field 8885.

Script chạy trong container alignment-tests, dùng chứng chỉ lab trong /clients.
Không in nội dung khóa riêng; chỉ đọc path và kiểm tra reason code MQTT 5.
"""

from __future__ import annotations

import argparse
import socket
import ssl
import sys
import time
from dataclasses import dataclass, field

from iot_protocol.topics import (
    alerts_topic,
    command_result_topic,
    status_topic,
    telemetry_topic,
)
from paho.mqtt import client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from paho.mqtt.properties import Properties, PacketTypes

SITE = "SITE_01"
DEVICE_TYPE = "light"
DEVICE_ID = "LGT_NODE_001"


@dataclass
class Seen:
    messages: list[tuple[str, bytes, bool]] = field(default_factory=list)

    def wait_for(self, topic: str, predicate, timeout: float = 10.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for seen_topic, payload, retain in list(self.messages):
                if seen_topic == topic and predicate(payload, retain):
                    return payload, retain
            time.sleep(0.05)
        raise AssertionError(f"không nhận được bản tin kỳ vọng trên {topic}")


def reason_value(reason) -> int:
    """paho 2.x trả ReasonCode, không phải int."""
    return reason.value if hasattr(reason, "value") else int(reason)


def on_connect(client, userdata, flags, reason_code, properties):
    del client, userdata, flags, properties
    if reason_value(reason_code) >= 0x80:
        raise AssertionError(f"CONNECT bị từ chối: {reason_code}")


def on_subscribe(client, userdata, mid, reason_codes, properties):
    del client, userdata, mid, properties
    for reason in reason_codes:
        if reason_value(reason) >= 0x80:
            raise AssertionError(f"SUBSCRIBE bị từ chối: {reason}")


def on_message(client, userdata, message):
    del client
    userdata.messages.append((message.topic, message.payload, message.retain))


def make_client(client_id: str, cert: str, key: str, seen: Seen | None) -> mqtt.Client:
    client = mqtt.Client(
        callback_api_version=CallbackAPIVersion.VERSION2,
        client_id=client_id,
        protocol=mqtt.MQTTv5,
    )
    # Không đặt username: broker lấy identity từ CN chứng chỉ mTLS.
    client.tls_set(
        ca_certs="/clients/server-ca.crt",
        certfile=cert,
        keyfile=key,
        tls_version=ssl.PROTOCOL_TLS_CLIENT,
    )
    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    if seen is not None:
        client.user_data_set(seen)
        client.on_message = on_message
    return client


def connect(client: mqtt.Client, host: str, port: int) -> None:
    client.connect(host, port, keepalive=15)
    client.loop_start()
    deadline = time.monotonic() + 10.0
    while not client.is_connected() and time.monotonic() < deadline:
        time.sleep(0.05)
    if not client.is_connected():
        raise AssertionError("không kết nối được broker field")


def publish(client: mqtt.Client, topic: str, payload: bytes, retain: bool = False) -> None:
    info = client.publish(topic, payload, qos=1, retain=retain)
    info.wait_for_publish(timeout=5)
    if info.rc != mqtt.MQTT_ERR_SUCCESS:
        raise AssertionError(f"publish {topic} thất bại: {info.rc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="mqtt.dev.pccom.test")
    parser.add_argument("--port", type=int, default=8885)
    args = parser.parse_args()

    telemetry = telemetry_topic(SITE, DEVICE_TYPE, DEVICE_ID)
    status = status_topic(SITE, DEVICE_TYPE, DEVICE_ID)
    alerts = alerts_topic(SITE, DEVICE_TYPE, DEVICE_ID)
    result = command_result_topic(SITE, DEVICE_TYPE, DEVICE_ID)
    expected = {
        "telemetry": "telemetry/v1/SITE_01/light/LGT_NODE_001",
        "status": "status/v1/SITE_01/light/LGT_NODE_001",
        "alerts": "alerts/v1/SITE_01/light/LGT_NODE_001",
        "result": "commands/v1/SITE_01/light/LGT_NODE_001/dim/result",
    }
    actual = {
        "telemetry": telemetry,
        "status": status,
        "alerts": alerts,
        "result": result,
    }
    if actual != expected:
        raise AssertionError(f"topic lệch Annex C: {actual} != {expected}")
    print("TOPICS: builder khớp telemetry/status/alerts/result")

    seen = Seen()
    device = make_client(
        "lab-align-device",
        f"/clients/dev_SITE_01_{DEVICE_ID}.crt",
        f"/clients/dev_SITE_01_{DEVICE_ID}.key",
        None,
    )
    connect(device, args.host, args.port)

    # Retain policy: telemetry retained bị plugin đổi thành non-retained. Kiểm tra
    # bằng client subscribe SAU publish: retained store không được có bản tin này.
    # (Bản tin live gửi tới subscriber cũ luôn có RETAIN=0 theo MQTT spec.)
    publish(device, telemetry, b"retained-must-be-cleared", retain=True)
    telemetry_seen = Seen()
    checker = make_client(
        "lab-align-telemetry-check",
        "/clients/field-bridge-s01.crt",
        "/clients/field-bridge-s01.key",
        telemetry_seen,
    )
    connect(checker, args.host, args.port)
    checker.subscribe(telemetry, qos=1)
    time.sleep(0.8)
    if telemetry_seen.messages:
        raise AssertionError("telemetry vẫn nằm trong retained store")
    print("RETAIN: telemetry bị đổi thành non-retained")

    # Status retained được phép: subscribe sau publish vẫn nhận online, RETAIN=1.
    publish(device, status, b"online", retain=True)
    status_seen = Seen()
    status_checker = make_client(
        "lab-align-status-check",
        "/clients/field-bridge-s01.crt",
        "/clients/field-bridge-s01.key",
        status_seen,
    )
    connect(status_checker, args.host, args.port)
    status_checker.subscribe(status, qos=1)
    payload, retain = status_seen.wait_for(status, lambda p, _r: p == b"online")
    if not retain:
        raise AssertionError("status retained bị policy chặn")
    print("RETAIN: status được giữ lại")

    # Broker dùng use_username_as_clientid: các cert cùng CN không được kết nối
    # đồng thời. Đóng checker rồi mới connect observer cho phép thử LWT.
    for client in (checker, status_checker):
        client.loop_stop()
        client.disconnect()
    observer = make_client(
        "lab-align-observer",
        "/clients/field-bridge-s01.crt",
        "/clients/field-bridge-s01.key",
        seen,
    )
    connect(observer, args.host, args.port)
    observer.subscribe(status, qos=1)
    time.sleep(0.5)

    # LWT: Will Delay Interval = 0, đóng socket đột ngột, observer nhận offline.
    will_props = Properties(PacketTypes.WILLMESSAGE)
    setattr(will_props, "Will Delay Interval", 0)
    victim = make_client(
        "lab-align-lwt",
        f"/clients/dev_SITE_01_{DEVICE_ID}.crt",
        f"/clients/dev_SITE_01_{DEVICE_ID}.key",
        None,
    )
    victim.will_set(status, b"offline", qos=1, retain=True, properties=will_props)
    connect(victim, args.host, args.port)
    time.sleep(0.2)
    victim_socket = getattr(victim, "_sock", None)
    if victim_socket is None:
        raise AssertionError("không lấy được socket để mô phỏng mất kết nối")
    closed_at = time.monotonic()
    try:
        victim_socket.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    victim_socket.close()
    victim.loop_stop()
    _payload, _live_retain = seen.wait_for(status, lambda p, _r: p == b"offline")
    elapsed = time.monotonic() - closed_at
    if elapsed > 10.0:
        raise AssertionError(f"LWT chậm: {elapsed:.2f}s (Will Delay Interval = 0)")
    lwt_seen = Seen()
    lwt_checker = make_client(
        "lab-align-lwt-check",
        "/clients/field-bridge-s01.crt",
        "/clients/field-bridge-s01.key",
        lwt_seen,
    )
    connect(lwt_checker, args.host, args.port)
    lwt_checker.subscribe(status, qos=1)
    _payload, retained = lwt_seen.wait_for(status, lambda p, _r: p == b"offline")
    if not retained:
        raise AssertionError("LWT offline không nằm trong retained store")
    print(f"LWT: offline retained sau {elapsed:.2f}s (Will Delay Interval = 0)")

    # Dọn retained status để lần chạy sau không lấy phải trạng thái cũ.
    # victim đã chiếm client ID của device cũ, nên dùng client mới để dọn retained.
    cleanup = make_client(
        "lab-align-cleanup",
        f"/clients/dev_SITE_01_{DEVICE_ID}.crt",
        f"/clients/dev_SITE_01_{DEVICE_ID}.key",
        None,
    )
    connect(cleanup, args.host, args.port)
    publish(cleanup, status, b"", retain=True)
    for client in (lwt_checker, observer, cleanup):
        client.loop_stop()
        client.disconnect()
    print("ALIGNMENT: PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as exc:
        print(f"ALIGNMENT: FAIL - {exc}", file=sys.stderr)
        sys.exit(1)
