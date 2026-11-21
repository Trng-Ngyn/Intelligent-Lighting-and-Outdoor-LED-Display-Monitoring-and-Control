"""Unit test cho bốn module điều khiển chiếu sáng Subtask 1."""
from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from lighting_control.contracts import ModuleStatus
from lighting_control.dali import (
    DaliAddress, DaliAddressType, DaliDevice, DaliDimmingController,
)
from lighting_control.fade import FadeController
from lighting_control.offline import OfflineFallbackManager
from lighting_control.thermal import ThermalDeratingEngine, ThermalState


class FakeDaliBus:
    def __init__(self, send_ok: bool = True) -> None:
        self.send_ok = send_ok
        self.arc_calls = []
        self.fade_calls = []

    def send_arc_power(self, address, arc_level):
        self.arc_calls.append((address, arc_level))
        return self.send_ok

    def set_fade_time(self, address, setting):
        self.fade_calls.append((address, setting))
        return self.send_ok


class DaliTests(unittest.TestCase):
    def setUp(self):
        self.bus = FakeDaliBus()
        self.device = DaliDevice("LGT_001", DaliAddress(DaliAddressType.SHORT, 0))
        self.controller = DaliDimmingController(self.bus, lambda pct, dev: round(pct * 2.54))
        self.controller.register_device(self.device)

    def test_dimming_sends_arc_power_but_marks_unverified(self):
        result = self.controller.set_brightness("LGT_001", 50)
        self.assertEqual(result.status, ModuleStatus.WARNING)
        self.assertEqual(result.state, "UNVERIFIED")
        self.assertEqual(self.bus.arc_calls[0][1], 127)

    def test_off_sends_arc_zero(self):
        self.controller.set_brightness("LGT_001", 0)
        self.assertEqual(self.bus.arc_calls[0][1], 0)

    def test_missing_curve_fails_closed(self):
        controller = DaliDimmingController(self.bus)
        controller.register_device(self.device)
        result = controller.set_brightness("LGT_001", 50)
        self.assertEqual(result.error.code, "CURVE_NOT_CONFIGURED")
        self.assertEqual(self.bus.arc_calls, [])

    def test_bus_failure_is_error(self):
        self.bus.send_ok = False
        result = self.controller.set_brightness("LGT_001", 50)
        self.assertEqual(result.status, ModuleStatus.ERROR)

    def test_fade_preset_uses_native_setting(self):
        fade = FadeController(
            lambda setting: self.controller.set_fade_time("LGT_001", setting),
            lambda target: self.controller.set_brightness("LGT_001", target),
        )
        result = fade.select_preset(1, 0, 100)
        self.assertEqual(self.bus.fade_calls[0][1], 5)
        self.assertEqual(result.output["nominal_duration_seconds"], 2.8)


class ThermalTests(unittest.TestCase):
    def setUp(self):
        self.engine = ThermalDeratingEngine()

    def test_derating_is_80_percent_of_original_request(self):
        result = self.engine.evaluate(80, 80, 10)
        self.assertEqual(result.output["final_brightness_pct"], 64)
        result2 = self.engine.evaluate(80, 80, 20)
        self.assertEqual(result2.output["final_brightness_pct"], 64)

    def test_exactly_75_c_does_not_derate_but_resets_recovery_timer(self):
        result = self.engine.evaluate(75, 80, 10)
        self.assertEqual(result.state, ThermalState.NORMAL.value)
        self.assertEqual(result.output["final_brightness_pct"], 80)

    def test_shutdown_above_90(self):
        result = self.engine.evaluate(90.1, 50, 10)
        self.assertTrue(result.output["shutdown_required"])
        self.assertEqual(result.output["final_brightness_pct"], 0)

    def test_recovery_requires_continuous_300_seconds_below_75(self):
        self.engine.evaluate(91, 50, 0)
        self.engine.evaluate(74, 50, 100)
        pending = self.engine.evaluate(74, 50, 399)
        self.assertEqual(pending.state, ThermalState.SHUTDOWN.value)
        recovered = self.engine.evaluate(74, 50, 400)
        self.assertEqual(recovered.state, ThermalState.NORMAL.value)

    def test_temperature_rise_resets_recovery_timer(self):
        self.engine.evaluate(91, 50, 0)
        self.engine.evaluate(74, 50, 100)
        self.engine.evaluate(75, 50, 200)
        self.engine.evaluate(74, 50, 798)
        pending = self.engine.evaluate(74, 50, 1097)
        self.assertEqual(pending.state, ThermalState.SHUTDOWN.value)
        recovered = self.engine.evaluate(74, 50, 1098)
        self.assertEqual(recovered.state, ThermalState.NORMAL.value)

    def test_invalid_sensor_is_not_assumed_safe(self):
        result = self.engine.evaluate(None, 50, 10, sensor_valid=False)
        self.assertEqual(result.state, ThermalState.SENSOR_FAULT.value)
        self.assertIsNone(result.output["final_brightness_pct"])


class OfflineTests(unittest.TestCase):
    def setUp(self):
        self.manager = OfflineFallbackManager()
        self.now = datetime(2026, 11, 18, 19, 0)

    def evaluate(self, seconds=301, **kwargs):
        values = dict(mqtt_connected=False, mqtt_disconnected_seconds=seconds,
                      local_time=self.now, clock_valid=True, lux=100,
                      sensor_valid=True, now_seconds=seconds)
        values.update(kwargs)
        return self.manager.evaluate(**values)

    def test_fallback_waits_until_more_than_300_seconds(self):
        result = self.evaluate(seconds=300)
        self.assertFalse(result.output["fallback_active"])
        result = self.evaluate(seconds=301)
        self.assertEqual(result.output["local_target_pct"], 100)

    def test_local_schedule_windows(self):
        for hour, minute, expected in [(23, 0, 70), (2, 0, 40), (6, 0, 0), (19, 0, 100)]:
            self.now = self.now.replace(hour=hour, minute=minute)
            self.assertEqual(self.evaluate().output["local_target_pct"], expected)

    def test_dawn_bright_requires_two_minutes(self):
        self.now = self.now.replace(hour=5, minute=0)
        first = self.evaluate(seconds=301, lux=100, now_seconds=0)
        second = self.evaluate(seconds=421, lux=100, now_seconds=120)
        self.assertEqual(first.output["local_target_pct"], 40)
        self.assertEqual(second.output["local_target_pct"], 0)

    def test_deadband_holds_previous_state(self):
        self.now = self.now.replace(hour=5, minute=0)
        self.evaluate(seconds=301, lux=100, now_seconds=0)
        result = self.evaluate(seconds=421, lux=65, now_seconds=120)
        self.assertEqual(result.output["local_target_pct"], 40)

    def test_sensor_fault_is_reported_not_zero_lux(self):
        self.now = self.now.replace(hour=5, minute=0)
        result = self.evaluate(sensor_valid=False, lux=None)
        self.assertEqual(result.status, ModuleStatus.WARNING)
        self.assertEqual(result.error.code, "AMBIENT_SENSOR_FAULT")
        self.assertEqual(result.output["local_target_pct"], 40)

    def test_invalid_clock_defers_safe_policy(self):
        result = self.evaluate(clock_valid=False)
        self.assertEqual(result.error.code, "RTC_INVALID")
        self.assertIsNone(result.output["local_target_pct"])


if __name__ == "__main__":
    unittest.main()
