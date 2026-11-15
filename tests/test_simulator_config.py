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

from edge_simulator.config import ConfigError, load_config

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

    def test_max_devices_env_override(self) -> None:
        with patch.dict(
            os.environ,
            {"SIM_MAX_DEVICES": "2"},
            clear=False,
        ):
            config = load_config(str(TEST_CONFIG))
        self.assertEqual(len(config.devices), 2)

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
