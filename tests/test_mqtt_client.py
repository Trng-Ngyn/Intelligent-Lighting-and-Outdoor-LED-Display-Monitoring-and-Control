"""Kiểm tra xử lý reason code MQTT 5 của Mqtt5Client."""

import logging
import threading
import unittest

import paho.mqtt.client as mqtt
from paho.mqtt.packettypes import PacketTypes

from edge_simulator.config import BrokerConfig
from edge_simulator.mqtt_client import Mqtt5Client, _reason_value


class Mqtt5ReasonCodeTests(unittest.TestCase):
    """Bảo đảm ACL deny không bị coi là publish/subscribe thành công."""

    def setUp(self) -> None:
        self.logger = logging.getLogger("test.mqtt5.reason")
        self.client = Mqtt5Client(
            BrokerConfig(host="localhost"),
            "test-reason-code",
            self.logger,
        )

    def test_puback_success_sets_reason_and_event(self) -> None:
        event = threading.Event()
        self.client._ack_events[7] = event

        self.client._handle_publish(None, None, 7, 16, None)

        self.assertTrue(event.is_set())
        self.assertEqual(self.client._ack_reasons[7], 16)

    def test_puback_failure_is_logged(self) -> None:
        with self.assertLogs(self.logger, level="ERROR") as captured:
            self.client._handle_publish(None, None, 8, 135, None)

        self.assertTrue(
            any("PUBACK/PUBCOMP từ chối" in line for line in captured.output)
        )
        self.assertEqual(self.client._ack_reasons[8], 135)

    def test_suback_failure_is_logged(self) -> None:
        self.client._subscribe_topics[9] = [
            "telemetry/v1/SITE_01/light/LGT_NODE_001"
        ]

        with self.assertLogs(self.logger, level="ERROR") as captured:
            self.client._handle_subscribe(None, None, 9, [135], None)

        self.assertTrue(
            any("SUBACK từ chối" in line for line in captured.output)
        )
        self.assertNotIn(9, self.client._subscribe_topics)

    def test_reason_value_supports_paho_reason_code(self) -> None:
        """Paho ReasonCode không int() trực tiếp; helper phải đọc .value."""
        reason = mqtt.ReasonCode(PacketTypes.PUBACK, "Not authorized")
        with self.assertRaises(TypeError):
            int(reason)  # bảo vệ giả định của regression test
        self.assertEqual(_reason_value(reason), 135)

    def test_puback_real_reason_code_failure_is_logged(self) -> None:
        reason = mqtt.ReasonCode(PacketTypes.PUBACK, "Not authorized")

        with self.assertLogs(self.logger, level="ERROR") as captured:
            self.client._handle_publish(None, None, 10, reason, None)

        self.assertTrue(
            any("PUBACK/PUBCOMP từ chối" in line for line in captured.output)
        )
        self.assertEqual(self.client._ack_reasons[10], 135)

    def test_suback_real_reason_code_failure_is_logged(self) -> None:
        topic = "telemetry/v1/SITE_01/light/LGT_NODE_001"
        self.client._subscribe_topics[11] = [topic]
        reason = mqtt.ReasonCode(PacketTypes.SUBACK, "Not authorized")

        with self.assertLogs(self.logger, level="ERROR") as captured:
            self.client._handle_subscribe(None, None, 11, [reason], None)

        self.assertTrue(
            any("SUBACK từ chối" in line for line in captured.output)
        )
        self.assertNotIn(11, self.client._subscribe_topics)


if __name__ == "__main__":
    unittest.main()
