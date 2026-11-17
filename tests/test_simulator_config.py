"""Unit test cho việc nạp config simulator.

Chạy cùng bộ:
    python -m unittest discover -s tests -p "test_*.py" -v
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from edge_simulator.config import ConfigError, NorthboundConfig, load_config

REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_CONFIG = REPO_ROOT / "tests" / "fixtures" / "simulator.test.json"
EXAMPLE_CONFIG = REPO_ROOT / "config.example.json"


class ConfigTests(unittest.TestCase):
    """Kiểm tra mở rộng thiết bị và override biến môi trường."""

    def test_load_test_config(self) -> None:
        config = load_config(str(TEST_CONFIG))
        self.assertEqual(config.broker.host, "broker.emqx.io")
        self.assertEqual(config.settings.keep_alive_sec, 15)
        self.assertEqual(len(config.devices), 3)
        keys = {device.key for device in config.devices}
        self.assertIn(("SITE_TEST_01", "light", "LGT_NODE_001"), keys)
        self.assertIn(
            ("SITE_TEST_01", "led_display", "DSP_LED_001"),
            keys,
        )

    def test_example_config_has_52_devices(self) -> None:
        config = load_config(str(EXAMPLE_CONFIG))
        self.assertEqual(len(config.devices), 52)

    def test_explicit_northbound_mapping(self) -> None:
        config = load_config(str(TEST_CONFIG))
        self.assertEqual(config.northbound.tenant_id, "t1")
        self.assertEqual(config.northbound_site("SITE_TEST_01"), "s01")
        self.assertEqual(config.gateway_for_site("SITE_TEST_01"), "gw-001")

    def test_northbound_mapping_defaults_from_site_number(self) -> None:
        config = NorthboundConfig()
        self.assertEqual(config.site_slug("SITE_03"), "s03")
        self.assertEqual(config.gateway_id("SITE_03"), "gw-003")
        self.assertEqual(config.gateway_id("SITE_02"), "gw-002")

    def test_max_devices_env_override(self) -> None:
        with patch.dict(
            os.environ,
            {"SIM_MAX_DEVICES": "2"},
            clear=False,
        ):
            config = load_config(str(TEST_CONFIG))
        self.assertEqual(len(config.devices), 2)

    def test_keep_alive_over_20_rejected(self) -> None:
        # 1,5 x keep_alive phải <= 30s ngân sách phát hiện offline của LWT.
        with patch.dict(
            os.environ,
            {"SIM_KEEP_ALIVE_SEC": "21"},
            clear=False,
        ):
            with self.assertRaises(ConfigError):
                load_config(str(TEST_CONFIG))

    def test_signing_secret_env_override(self) -> None:
        with patch.dict(
            os.environ,
            {"SIM_SIGNING_SECRET": "override-secret-123456789"},
            clear=False,
        ):
            config = load_config(str(TEST_CONFIG))
        self.assertEqual(
            config.security.signing_secret,
            "override-secret-123456789",
        )

    def test_tls_client_cert_env_override(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SIM_BROKER_TLS": "true",
                "SIM_BROKER_CA_CERT": "certs/ca.pem",
                "SIM_BROKER_CLIENT_CERT": "certs/client.pem",
                "SIM_BROKER_CLIENT_KEY": "certs/client.key",
                "SIM_BROKER_TLS_INSECURE": "true",
            },
            clear=False,
        ):
            config = load_config(str(TEST_CONFIG))
        self.assertTrue(config.broker.use_tls)
        self.assertEqual(config.broker.ca_cert, "certs/ca.pem")
        self.assertEqual(config.broker.client_cert, "certs/client.pem")
        self.assertEqual(config.broker.client_key, "certs/client.key")
        self.assertTrue(config.broker.tls_insecure)

    def test_tls_client_cert_requires_key(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SIM_BROKER_TLS": "true",
                "SIM_BROKER_CLIENT_CERT": "certs/client.pem",
            },
            clear=False,
        ):
            with self.assertRaises(ConfigError):
                load_config(str(TEST_CONFIG))

    def test_tls_files_require_tls_enabled(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SIM_BROKER_CA_CERT": "certs/ca.pem",
            },
            clear=False,
        ):
            with self.assertRaises(ConfigError):
                load_config(str(TEST_CONFIG))

    def test_missing_config_raises(self) -> None:
        with self.assertRaises(ConfigError):
            load_config(str(REPO_ROOT / "does-not-exist.json"))

    def test_short_secret_rejected(self) -> None:
        with patch.dict(
            os.environ,
            {"SIM_SIGNING_SECRET": "short"},
            clear=False,
        ):
            with self.assertRaises(ConfigError):
                load_config(str(TEST_CONFIG))


if __name__ == "__main__":
    unittest.main()
