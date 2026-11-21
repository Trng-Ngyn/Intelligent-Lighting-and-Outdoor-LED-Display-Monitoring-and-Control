"""Unit test cho Safety Supervisor – Subtask 2."""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from lighting_control.safety import FaultManager, SafetyAction, SafetySupervisor, SystemState


class FaultManagerTests(unittest.TestCase):
    def test_raise_update_and_clear_fault(self):
        manager = FaultManager()
        first = manager.raise_fault("TEMP", "CRITICAL", "Thermal", "sensor lost")
        updated = manager.raise_fault("TEMP", "HIGH", "Thermal", "still lost")
        self.assertEqual(first.fault_code, updated.fault_code)
        self.assertEqual(len(manager.active_faults()), 1)
        self.assertEqual(manager.active_faults()[0].fault_level, "HIGH")
        manager.clear_fault("TEMP")
        self.assertEqual(manager.active_faults(), [])


class SafetySupervisorTests(unittest.TestCase):
    def setUp(self):
        self.supervisor = SafetySupervisor()

    def test_normal_operation_allows_requested_brightness(self):
        d = self.supervisor.evaluate(requested_brightness_pct=80, temperature_c=30,
                                     temperature_sensor_valid=True)
        self.assertEqual(d.action, SafetyAction.ALLOW.value)
        self.assertEqual(d.final_brightness_pct, 80)
        self.assertEqual(d.system_state, SystemState.NORMAL.value)

    def test_schedule_caps_operator_request(self):
        d = self.supervisor.evaluate(requested_brightness_pct=80, schedule_brightness_pct=60,
                                     temperature_c=30, temperature_sensor_valid=True)
        self.assertEqual(d.final_brightness_pct, 60)
        self.assertEqual(d.action, SafetyAction.LIMIT.value)

    def test_sensor_fault_uses_30_percent_cap(self):
        d = self.supervisor.evaluate(requested_brightness_pct=100, schedule_brightness_pct=100,
                                     temperature_sensor_valid=False, last_valid_brightness_pct=70)
        self.assertEqual(d.final_brightness_pct, 30)
        self.assertIn("TEMPERATURE_SENSOR_FAULT_FIXED_30_CAP", d.reason_codes)

    def test_sensor_fault_does_not_force_light_on_when_schedule_off(self):
        d = self.supervisor.evaluate(requested_brightness_pct=100, schedule_brightness_pct=0,
                                     temperature_sensor_valid=False, last_valid_brightness_pct=70)
        self.assertEqual(d.final_brightness_pct, 0)
        self.assertEqual(d.action, SafetyAction.LIMIT.value)

    def test_hardware_critical_fault_overrides_temperature_sensor_fault(self):
        d = self.supervisor.evaluate(requested_brightness_pct=100,
                                     temperature_sensor_valid=False,
                                     hardware_faults=["POWER_STAGE_OVERCURRENT"])
        self.assertEqual(d.final_brightness_pct, 0)
        self.assertEqual(d.action, SafetyAction.SHUTDOWN.value)
        self.assertEqual(d.system_state, SystemState.FAULT_SHUTDOWN.value)

    def test_temperature_over_90_shuts_down(self):
        d = self.supervisor.evaluate(requested_brightness_pct=100, temperature_c=91,
                                     temperature_sensor_valid=True)
        self.assertEqual(d.final_brightness_pct, 0)
        self.assertEqual(d.action, SafetyAction.SHUTDOWN.value)

    def test_thermal_recovery_pending_keeps_output_off(self):
        d = self.supervisor.evaluate(requested_brightness_pct=100, temperature_c=74,
                                     temperature_sensor_valid=True,
                                     thermal_recovery_pending=True)
        self.assertEqual(d.final_brightness_pct, 0)
        self.assertEqual(d.system_state, SystemState.RECOVERY_PENDING.value)
        self.assertEqual(d.action, SafetyAction.SHUTDOWN.value)

    def test_derating_applies_to_original_requested_brightness(self):
        d = self.supervisor.evaluate(requested_brightness_pct=80, temperature_c=80,
                                     temperature_sensor_valid=True)
        self.assertEqual(d.final_brightness_pct, 64)
        self.assertEqual(d.system_state, SystemState.DERATING.value)

    def test_ambient_sensor_fault_holds_last_valid_target(self):
        d = self.supervisor.evaluate(requested_brightness_pct=80,
                                     last_valid_brightness_pct=45, temperature_c=30,
                                     ambient_sensor_valid=False)
        self.assertEqual(d.final_brightness_pct, 45)
        self.assertEqual(d.action, SafetyAction.HOLD.value)

    def test_ambient_sensor_fault_without_saved_target_fails_off(self):
        d = self.supervisor.evaluate(requested_brightness_pct=80,
                                     last_valid_brightness_pct=None,
                                     ambient_sensor_valid=False, temperature_c=30)
        self.assertEqual(d.final_brightness_pct, 0)

    def test_rtc_fault_holds_last_valid_target(self):
        d = self.supervisor.evaluate(requested_brightness_pct=80,
                                     last_valid_brightness_pct=55, temperature_c=30, rtc_valid=False)
        self.assertEqual(d.final_brightness_pct, 55)
        self.assertEqual(d.action, SafetyAction.HOLD.value)
        self.assertFalse(d.execution_authorized)

    def test_mqtt_loss_uses_local_schedule_after_300_seconds(self):
        d = self.supervisor.evaluate(requested_brightness_pct=90,
                                     schedule_brightness_pct=40,
                                     mqtt_connected=False,
                                     mqtt_disconnected_seconds=301, temperature_c=30,
                                     local_schedule_valid=True)
        self.assertEqual(d.final_brightness_pct, 40)
        self.assertEqual(d.system_state, SystemState.OFFLINE_FALLBACK.value)

    def test_offline_without_schedule_holds(self):
        d = self.supervisor.evaluate(requested_brightness_pct=90,
                                     last_valid_brightness_pct=35,
                                     mqtt_connected=False,
                                     mqtt_disconnected_seconds=301,
                                     local_schedule_valid=False)
        self.assertEqual(d.final_brightness_pct, 35)
        self.assertEqual(d.action, SafetyAction.HOLD.value)

    def test_dali_bus_fault_holds_logical_target_and_marks_unknown(self):
        d = self.supervisor.evaluate(requested_brightness_pct=80,
                                     last_valid_brightness_pct=50, dali_bus_ok=False)
        self.assertEqual(d.final_brightness_pct, 50)
        self.assertEqual(d.action, SafetyAction.HOLD.value)
        self.assertEqual(d.diagnostics["physical_output"], "UNKNOWN")

    def test_fade_fault_prevents_new_execution(self):
        d = self.supervisor.evaluate(requested_brightness_pct=80,
                                     last_valid_brightness_pct=50, fade_controller_ok=False)
        self.assertEqual(d.action, SafetyAction.HOLD.value)
        self.assertFalse(d.execution_authorized)

    def test_invalid_command_is_rejected(self):
        d = self.supervisor.evaluate(requested_brightness_pct=80,
                                     last_valid_brightness_pct=50, command_valid=False)
        self.assertEqual(d.action, SafetyAction.REJECT.value)
        self.assertFalse(d.execution_authorized)
        self.assertEqual(d.final_brightness_pct, 50)

    def test_replay_is_rejected(self):
        d = self.supervisor.evaluate(requested_brightness_pct=80,
                                     last_valid_brightness_pct=50, replay_detected=True)
        self.assertEqual(d.action, SafetyAction.REJECT.value)
        self.assertIn("COMMAND_REPLAY_REJECTED", d.reason_codes)

    def test_no_valid_boot_state_starts_off(self):
        d = self.supervisor.evaluate(requested_brightness_pct=80,
                                     boot_state_valid=False,
                                     last_valid_brightness_pct=None)
        self.assertEqual(d.final_brightness_pct, 0)
        self.assertEqual(d.system_state, SystemState.INITIALIZING.value)
        self.assertEqual(d.action, SafetyAction.SHUTDOWN.value)

    def test_sensor_fault_and_dali_fault_hold_prior_target_capped_at_30(self):
        # Bus lỗi: không thể phát lệnh; không tuyên bố thiết bị vật lý đã về 30%.
        d = self.supervisor.evaluate(requested_brightness_pct=90,
                                     last_valid_brightness_pct=60,
                                     temperature_sensor_valid=False,
                                     dali_bus_ok=False)
        self.assertEqual(d.action, SafetyAction.HOLD.value)
        self.assertEqual(d.final_brightness_pct, 60)
        self.assertEqual(d.diagnostics["physical_output"], "UNKNOWN")

    def test_module_error_is_included_in_active_faults(self):
        from lighting_control.contracts import ErrorInfo, ModuleResult, ModuleStatus
        result = ModuleResult("FadeController", ModuleStatus.ERROR, "ERROR",
                              error=ErrorInfo("FADE_IO", "fade failure", "HIGH"))
        d = self.supervisor.evaluate(requested_brightness_pct=30, module_results=[result])
        self.assertTrue(any(f["fault_code"] == "FADE_IO" for f in d.active_faults))

    def test_thermal_module_result_drives_sensor_fault_policy(self):
        from lighting_control.contracts import ErrorInfo, ModuleResult, ModuleStatus
        result = ModuleResult("ThermalDeratingEngine", ModuleStatus.ERROR, "SENSOR_FAULT",
                              error=ErrorInfo("TEMPERATURE_SENSOR_FAULT", "sensor lost", "CRITICAL"))
        d = self.supervisor.evaluate(requested_brightness_pct=90, temperature_c=None,
                                     module_results=[result])
        self.assertEqual(d.final_brightness_pct, 30)
        self.assertIn("TEMPERATURE_SENSOR_FAULT", [f["fault_code"] for f in d.active_faults])

    def test_dali_controller_error_from_module_result_blocks_execution(self):
        from lighting_control.contracts import ErrorInfo, ModuleResult, ModuleStatus
        result = ModuleResult("DaliDimmingController", ModuleStatus.ERROR, "ERROR",
                              error=ErrorInfo("CURVE_NOT_CONFIGURED", "mapper missing", "HIGH"))
        d = self.supervisor.evaluate(requested_brightness_pct=60,
                                     last_valid_brightness_pct=40,
                                     module_results=[result])
        self.assertEqual(d.action, SafetyAction.HOLD.value)
        self.assertFalse(d.execution_authorized)
        self.assertEqual(d.final_brightness_pct, 40)

    def test_offline_module_result_supplies_local_schedule_target(self):
        from lighting_control.contracts import ModuleResult, ModuleStatus
        result = ModuleResult("OfflineFallbackManager", ModuleStatus.SUCCESS, "LOCAL_SCHEDULE",
                              input={"mqtt_connected": False},
                              output={"fallback_active": True, "local_target_pct": 40})
        d = self.supervisor.evaluate(requested_brightness_pct=90,
                                     temperature_c=30, module_results=[result])
        self.assertEqual(d.final_brightness_pct, 40)
        self.assertEqual(d.system_state, SystemState.OFFLINE_FALLBACK.value)

    def test_result_contract_contains_required_fields(self):
        data = self.supervisor.evaluate(requested_brightness_pct=50).to_dict()
        for key in ("decision_id", "timestamp", "system_state", "requested_brightness_pct",
                    "final_brightness_pct", "action", "execution_authorized",
                    "active_faults", "reason_codes", "diagnostics"):
            self.assertIn(key, data)


if __name__ == "__main__":
    unittest.main()
