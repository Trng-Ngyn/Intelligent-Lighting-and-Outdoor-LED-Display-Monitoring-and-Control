"""Offline Draft-07 contract candidates. All fixture identities and values are test data."""

import ast
import json
import unittest
from copy import deepcopy
from functools import cached_property
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from jsonschema import Draft7Validator, FormatChecker
from referencing import Registry


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data_contracts"
ID = "00000000-0000-4000-a000-000000000001"
TIME = "2026-01-02T12:00:00Z"
BAD_DATE = "2026-02-30T12:00:00Z"
ACTOR = {"kind": "user", "id": ID}
TARGET = {"kind": "asset", "id": ID}
DELETE = object()
MAX_SEQUENCE = 9007199254740991
FORMAT = FormatChecker(formats=["date-time"])


@FORMAT.checks("iana-time-zone", raises=(ZoneInfoNotFoundError, ValueError))
def known_time_zone(value):
    if isinstance(value, str):
        ZoneInfo(value)
    return True


def metric(value, unit, quality="estimated"):
    return {"value": value, "unit": unit, "quality": quality}


class Candidate:
    """Fixed fixture keys also serve as the reviewed required-field baseline."""

    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads((DATA / cls.filename).read_text(encoding="utf-8"))
        cls.validator = Draft7Validator(cls.schema, registry=Registry(), format_checker=FORMAT)

    @cached_property
    def fixture(self):
        return self.make_fixture()

    def positive(self, payload, label):
        with self.subTest(expect="accept", case=label):
            self.assertEqual(list(self.validator.iter_errors(payload)), [])

    def change(self, control, path, value, keyword=None, *, cause=None, membership=False, also=()):
        """Mutate one field; report object-level keywords at the containing object."""
        self.assertEqual(list(self.validator.iter_errors(control)), [])
        payload = deepcopy(control)
        keys = path.split(".")
        parent = payload
        for key in keys[:-1]:
            parent = parent[key]
        if value is DELETE:
            del parent[keys[-1]]
        else:
            parent[keys[-1]] = value
        expected = "reject" if keyword else "accept"
        with self.subTest(expect=expected, field=path, mutation="delete" if value is DELETE else value):
            errors = list(self.validator.iter_errors(payload))
            pairs = [(tuple(e.absolute_path), e.validator) for e in errors]
            if not keyword:
                self.assertEqual(pairs, [])
                return
            location = keys[:-1] if keyword in ("required", "additionalProperties", "not") else keys
            error = (tuple(location), keyword)
            if membership:
                self.assertIn(error, pairs)
            else:
                self.assertCountEqual(pairs, [error, *also])
            if cause:
                outer = errors[pairs.index(error)]
                self.assertIn(cause, [(tuple(e.absolute_path), e.validator) for e in outer.context])

    def test_schema_integrity(self):
        self.assertEqual(self.schema["$schema"], Draft7Validator.META_SCHEMA["$id"])
        Draft7Validator.check_schema(self.schema)

    def test_fixture(self):
        self.positive(self.fixture, "primary fixture")

    def test_required_fields(self):
        self.assertCountEqual(self.schema["required"], self.required)
        for name in self.required:
            self.change(self.fixture, name, DELETE, "required", membership=True)


class Normalized(Candidate):
    def make_fixture(self):
        return dict(schema_version=1, message_type=self.message, tenant_id=ID, site_id=ID,
                    **deepcopy(self.fields))

    @property
    def required(self):
        return ("schema_version", "message_type", "tenant_id", "site_id", *self.fields)

    def test_envelope(self):
        self.change(self.fixture, "schema_version", 2, "const")
        self.change(self.fixture, "message_type", self.other_message, "const")
        self.change(self.fixture, "tenant_id", ID.upper(), "pattern")
        self.change(self.fixture, "extra", True, "additionalProperties")
        for name in self.timestamps:
            self.change(self.fixture, name, BAD_DATE, "format")
            self.change(self.fixture, name, TIME.replace("Z", "+00:00"), "pattern")


class Telemetry(Normalized):
    fields = dict(asset_id=ID, device_id=ID, message_id=ID, source_time=TIME, received_time=TIME,
                  sequence=0, firmware="lab", clock_quality="uncertain",
                  metrics={"power_w": metric(0, "W")})
    timestamps = ("source_time", "received_time")

    def test_metric_shape_and_quality(self):
        self.change(self.fixture, "metrics", {}, "minProperties")
        self.change(self.fixture, "metrics.extra", {}, "additionalProperties")
        leaf = self.schema["properties"]["metrics"]["properties"]["power_w"]
        self.assertCountEqual(leaf["required"], ("value", "quality", "unit"))
        for name in ("value", "quality", "unit"):
            self.change(self.fixture, "metrics.power_w." + name, DELETE, "required", membership=True)
        self.change(self.fixture, "metrics.power_w.unit", "Wh", "const")
        self.change(self.fixture, "metrics.power_w.value", 1000000, None)
        self.change(self.fixture, "metrics.power_w.value", 1000001, "maximum")
        self.change(self.fixture, "metrics.power_w.value", None, "type")
        self.change(self.fixture, "metrics.power_w.quality", "measured")
        for quality in ("unavailable", "invalid", "stuck"):
            control = dict(self.fixture, metrics={"power_w": metric(None, "W", quality)})
            self.positive(control, quality)
            self.change(control, "metrics.power_w.value", 0, "type")
        self.change(control, "metrics.power_w.quality", "simulated", "enum")

    def test_sequence_clock_and_energy_context(self):
        self.change(self.fixture, "sequence", MAX_SEQUENCE)
        self.change(self.fixture, "sequence", MAX_SEQUENCE + 1, "maximum")
        self.change(self.fixture, "sequence", -1, "minimum")
        self.change(self.fixture, "clock_quality", "good", "enum")
        for name, field, value in [("energy_interval_wh", "energy_interval_start", "2026-01-02T11:00:00Z"),
                                   ("energy_register_wh", "counter_epoch", ID)]:
            control = dict(self.fixture, metrics={name: metric(1, "Wh")}, **{field: value})
            self.positive(control, name)
            self.change(control, field, DELETE, "required")
            self.change(self.fixture, field, value, "not")


class LightingTelemetrySchemaTests(Telemetry, unittest.TestCase):
    message = "telemetry.lighting"
    other_message = "telemetry.led"
    filename = "schemas/telemetry.lighting.v1.schema.json"

    def test_lighting_metrics(self):
        control = dict(self.fixture, metrics={"dimming_pct": metric(100, "%"), "is_on": metric(False, "1")})
        self.positive(control, "synthetic dimming and power")
        self.change(control, "metrics.dimming_pct.value", 101, "maximum")
        self.change(control, "metrics.is_on.value", 1, "type")
        self.change(control, "metrics.player_health", metric("ok", "1"), "additionalProperties")


class LedTelemetrySchemaTests(Telemetry, unittest.TestCase):
    message = "telemetry.led"
    other_message = "telemetry.lighting"
    filename = "schemas/telemetry.led.v1.schema.json"

    def test_player_metadata(self):
        control = dict(self.fixture, metrics={"player_health": metric("ok", "1"),
                                             "playback_position_ms": metric(0, "ms"),
                                             "active_manifest_id": metric(ID, "1")})
        self.positive(control, "player snapshot")
        self.change(control, "metrics.player_health.value", "running", "enum")
        self.change(control, "metrics.playback_position_ms.value", -1, "minimum")
        self.change(control, "metrics.active_manifest_id.value", ID.upper(), "pattern")
        self.change(control, "metrics.is_on", metric(True, "1"), "additionalProperties")


class CommandRequestSchemaTests(Normalized, unittest.TestCase):
    message = "command.request"
    other_message = "command.result"
    filename = "schemas/command.request.v1.schema.json"
    timestamps = ("issued_at", "expires_at")
    fields = dict(command_id=ID, actor=ACTOR, target=TARGET, action="set_power", requested_value=True,
                  policy_version="p1", issued_at=TIME, expires_at="2026-01-02T12:01:00Z",
                  priority="operator", approval_required=False, approval_ref=None)

    def test_actions(self):
        self.change(self.fixture, "requested_value", 1, "type")
        self.change(self.fixture, "action", "set_level", "enum")
        for action in ("set_dimming", "set_brightness"):
            control = dict(self.fixture, action=action, requested_value=0)
            self.positive(control, action)
            self.change(control, "requested_value", 100)
            self.change(control, "requested_value", 101, "maximum")
        for action, parameters in [
            ("apply_schedule", dict(schedule_id=ID, schedule_version=1, time_zone="UTC")),
            ("activate_manifest", dict(manifest_id=ID, version=1, sha256="a" * 64)),
            ("revoke_manifest", dict(manifest_id=ID, revocation_version=1)),
        ]:
            control = dict(self.fixture, action=action, requested_value=parameters,
                           approval_required=True, approval_ref=ID)
            self.positive(control, action)
            for field in parameters:
                self.change(control, "requested_value." + field, DELETE, "required")
            if action == "apply_schedule":
                self.change(control, "requested_value.time_zone", "Example/Unknown", "format")
                self.change(control, "requested_value.schedule_version", 0, "minimum")
            else:
                self.change(control, "approval_required", False, "const", membership=True)
        for part in ("actor", "target"):
            for field in ("kind", "id"):
                self.change(self.fixture, part + "." + field, DELETE, "required")

    def test_approval_policy_shape(self):
        self.change(self.fixture, "approval_ref", ID, "type")
        control = dict(self.fixture, approval_required=True, approval_ref=ID)
        self.change(control, "approval_ref", None, "type")
        for priority in ("approved_override", "emergency"):
            control = dict(self.fixture, priority=priority, approval_required=True, approval_ref=ID)
            self.positive(control, priority)
            self.change(control, "approval_required", False, "const", membership=True)


class CommandResultSchemaTests(Normalized, unittest.TestCase):
    message = "command.result"
    other_message = "command.request"
    filename = "schemas/command.result.v1.schema.json"
    timestamps = ("received_time",)
    fields = dict(result_id=ID, command_id=ID, asset_id=ID, device_id=ID, device_time=None,
                  received_time=TIME, clock_quality="uncertain", status="acknowledged", reason=None,
                  observed_value=None, evidence_source="none")

    def test_status_and_clock(self):
        self.change(self.fixture, "status", "stored", "enum")
        # Non-none evidence also activates the observation-object branch.
        self.change(self.fixture, "evidence_source", "device_reported", "const",
                    also=[(("observed_value",), "oneOf")])
        self.change(self.fixture, "observed_value", {"kind": "power", "value": True}, "type")
        self.change(dict(self.fixture, clock_quality="synced", device_time=TIME), "device_time", None, "type")
        self.change(self.fixture, "status", "executed")
        for status in ("rejected", "expired", "failed", "unknown"):
            control = dict(self.fixture, status=status, reason="synthetic")
            self.positive(control, status)
            self.change(control, "reason", None, "type")

    def test_verification_and_player_evidence(self):
        control = dict(self.fixture, status="verified", clock_quality="synced", device_time=TIME,
                       observed_value={"kind": "manifest_id", "value": ID}, evidence_source="player_reported")
        self.positive(control, "verified player report")
        self.change(control, "clock_quality", "uncertain", "const")
        self.change(control, "observed_value.kind", "schedule_id", "const")
        control = dict(control, evidence_source="independent_sensor",
                       observed_value={"kind": "dimming_pct", "value": 100})
        self.positive(control, "verified percentage")
        self.change(control, "observed_value", {"kind": "dimming_pct", "value": 101}, "oneOf",
                    membership=True, cause=(("observed_value", "value"), "maximum"))


class AuditEventSchemaTests(Normalized, unittest.TestCase):
    message = "audit.event"
    other_message = "command.result"
    filename = "schemas/audit.event.v1.schema.json"
    timestamps = ("occurred_at", "recorded_at")
    fields = dict(event_id=ID, occurred_at=TIME, recorded_at=TIME, category="security", action="review",
                  actor=ACTOR, requested_by=None, approved_by=None, executed_by=None, target=TARGET,
                  command_id=None, approval_ref=None, correlation_id=ID, policy_version=None,
                  policy_decision="not_applicable", outcome="success", reason=None, final_state=None)

    def test_actor_target_and_decision(self):
        for part in ("actor", "target"):
            for field in ("id", "kind"):
                self.change(self.fixture, part + "." + field, DELETE, "required")
        for outcome in ("denied", "failed", "unknown"):
            control = dict(self.fixture, outcome=outcome, reason="synthetic")
            self.positive(control, outcome)
            self.change(control, "reason", None, "type")
        control = dict(self.fixture, policy_decision="deny", outcome="denied", reason="synthetic")
        self.positive(control, "deny")
        self.change(control, "outcome", "success", "const")

    def test_control_and_publication_context(self):
        control = dict(self.fixture, category="control", command_id=ID, requested_by=ACTOR,
                       policy_version="p1")
        self.positive(control, "control")
        for field in ("command_id", "requested_by", "policy_version"):
            self.change(control, field, None, "type")
        publication = dict(self.fixture, category="publication", requested_by=ACTOR, approved_by=ACTOR,
                           executed_by=ACTOR, approval_ref=ID, policy_version="p1")
        self.positive(publication, "publication shape")
        for field in ("requested_by", "approved_by", "executed_by", "approval_ref", "policy_version"):
            self.change(publication, field, None, "type")
        state = {"observed_at": TIME, "observation": {"kind": "power", "value": False},
                 "evidence_source": "device_reported"}
        self.change(self.fixture, "final_state", state)
        self.change(dict(self.fixture, final_state=state), "final_state", {},
                    "anyOf", cause=(("final_state",), "required"))


class AggregateTelemetrySchemaTests(Candidate, unittest.TestCase):
    filename = "schemas.json"
    required = ("schema_version", "message_id", "asset_id", "sequence", "source_time", "metrics", "quality")

    def make_fixture(self):
        # Read the original G0 literal without importing or executing the bench script.
        tree = ast.parse((ROOT / "tests/bench_tests_g0.py").read_text(encoding="utf-8"))
        function = next(f for f in tree.body if isinstance(f, ast.FunctionDef)
                        and f.name == "test_telemetry_schema_validation")
        assignment, = [s for s in function.body if isinstance(s, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == "sample_payload" for t in s.targets)]
        return ast.literal_eval(assignment.value)

    def test_metrics_and_extensions(self):
        required = ("power_w", "energy_wh", "voltage_v", "current_a", "temperature_c", "ambient_lux")
        self.assertCountEqual(self.schema["properties"]["metrics"]["required"], required)
        for name in required:
            self.change(self.fixture, "metrics." + name, DELETE, "required")
        self.change(self.fixture, "extension", True)
        self.change(self.fixture, "metrics.extension", "synthetic")
        for path, value, keyword in [
            ("schema_version", "1", "enum"), ("sequence", 0, "minimum"), ("source_time", TIME, "type"),
            ("quality", "measured", "enum"), ("relay_state", 1, "type"), ("brightness_pct", 100, None),
            ("brightness_pct", 101, "maximum"), ("metrics.voltage_v", 301, "maximum"),
            ("metrics.temperature_c", -21, "minimum"), ("metrics.power_factor", DELETE, None),
        ]:
            self.change(self.fixture, path, value, keyword)
