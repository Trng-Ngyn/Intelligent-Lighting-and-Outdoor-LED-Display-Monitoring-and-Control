"""Offline tests for the five repository contract candidates (DEP-07)."""

import json
import unittest
from copy import deepcopy
from functools import cached_property
from pathlib import Path

from referencing import Registry
from jsonschema import Draft202012Validator, FormatChecker


CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"
IDENTIFIERS = ("tenant_id", "site_id", "gateway_id", "message_id", "asset_id", "metric")
REQUIRED = ("schema_version", "environment", *IDENTIFIERS, "source_time",
            "sequence", "value", "unit", "quality", "firmware")


class CandidateTests:
    """Shared contract checks; only concrete unittest.TestCase classes are discovered."""

    @classmethod
    def setUpClass(cls):
        path = CONTRACTS / f"{cls.candidate}.schema.json"
        cls.schema = json.loads(path.read_text(encoding="utf-8"))
        cls.validator = Draft202012Validator(
            cls.schema, registry=Registry(), format_checker=FormatChecker(formats=["date-time"])
        )

    @cached_property
    def example(self):
        path = CONTRACTS / "examples" / f"{self.candidate}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assert_valid(payload)
        return payload

    def errors(self, payload):
        return [(tuple(e.absolute_path), e.validator) for e in self.validator.iter_errors(payload)]

    def assert_valid(self, payload):
        self.assertEqual(self.errors(payload), [])

    def assert_rejected(self, payload, *expected):
        self.assertCountEqual(self.errors(payload), expected)

    def test_dialect_and_metaschema(self):
        self.assertEqual(self.schema["$schema"], Draft202012Validator.META_SCHEMA["$id"])
        Draft202012Validator.check_schema(self.schema)

    def test_existing_example(self):
        self.assert_valid(self.example)

    def test_required_fields(self):
        self.assertCountEqual(self.schema["required"], self.required)
        for field in self.required:
            with self.subTest(field=field):
                payload = deepcopy(self.example)
                del payload[field]
                # Removing a discriminator may also activate conditional branches.
                self.assertIn(((), "required"), self.errors(payload))

    def check_changes(self, cases, control=None):
        """Each row replaces one root property of a known valid control."""
        if control is None:
            control = self.example
        self.assert_valid(control)
        for field, value, keyword in cases:
            with self.subTest(field=field, value=value, keyword=keyword):
                payload = deepcopy(control)
                payload[field] = value
                if keyword is None:
                    self.assert_valid(payload)
                else:
                    path = () if keyword == "additionalProperties" else (field,)
                    self.assert_rejected(payload, (path, keyword))


class TelemetrySchemaTests(CandidateTests, unittest.TestCase):
    candidate = "telemetry"

    def test_required_fields(self):
        self.assertCountEqual(self.schema["required"], REQUIRED)
        for field in REQUIRED:
            with self.subTest(field=field):
                payload = deepcopy(self.example)
                del payload[field]
                expected = [((), "required")]
                if field == "quality":
                    # Both if/properties clauses match an absent quality. The
                    # example's numeric value also fails the missing/null branch.
                    expected.append((("value",), "type"))
                self.assert_rejected(payload, *expected)

    def test_root_type_and_unknown_property(self):
        with self.subTest(case="root type"):
            self.assert_rejected([], ((), "type"))
        with self.subTest(case="extra field"):
            payload = deepcopy(self.example)
            payload["unknown"] = True
            self.assert_rejected(payload, ((), "additionalProperties"))

    def test_valid_field_boundaries(self):
        for field, values in [
            *((field, ("a", "a" * 64)) for field in (*IDENTIFIERS, "firmware")),
            ("sequence", (0, 9007199254740991)),
            ("value", ("", "x" * 120)),
        ]:
            for value in values:
                with self.subTest(field=field, value=value):
                    payload = deepcopy(self.example)
                    payload[field] = value
                    self.assert_valid(payload)

    def test_invalid_field_values(self):
        cases = [
            ("schema_version", 2, ("const",)),
            ("environment", "unknown", ("enum",)),
            ("unit", "unknown", ("enum",)),
            ("quality", "unknown", ("enum",)),
            ("sequence", -1, ("minimum",)),
            ("sequence", 9007199254740992, ("maximum",)),
            ("sequence", 1.5, ("type",)),
            ("source_time", 0, ("type",)),
            ("source_time", "2026-02-30T14:00:00Z", ("format",)),
            ("source_time", "2026-11-14T14:00:00+00:00", ("pattern",)),
            ("value", "x" * 121, ("maxLength",)),
            ("firmware", "", ("minLength",)),
            ("firmware", "a" * 65, ("maxLength",)),
            ("firmware", 1, ("type",)),
        ]
        for field in IDENTIFIERS:
            cases.extend([
                (field, "", ("minLength", "pattern")),
                (field, "a" * 65, ("maxLength",)),
                (field, "A", ("pattern",)),
                (field, 1, ("type",)),
            ])
        for field, value, keywords in cases:
            with self.subTest(field=field, value=value):
                payload = deepcopy(self.example)
                payload[field] = value
                self.assert_rejected(payload, *[((field,), keyword) for keyword in keywords])

    def test_valid_quality_value_pairs(self):
        for quality, values in [
            ("missing", (None,)),
            ("measured", (0, False, "ok")),
            ("estimated", (1.5, True, "ok")),
            ("invalid", (None,)),
        ]:
            for value in values:
                with self.subTest(quality=quality, value=value):
                    payload = deepcopy(self.example)
                    payload.update(quality=quality, value=value)
                    self.assert_valid(payload)

    def test_invalid_quality_value_pairs(self):
        for quality, valid, invalid in [
            ("missing", None, 0),
            ("measured", 0, None),
            ("estimated", 0, None),
            ("invalid", None, {}),
            ("invalid", None, []),
        ]:
            with self.subTest(quality=quality, invalid=invalid):
                payload = deepcopy(self.example)
                payload.update(quality=quality, value=valid)
                self.assert_valid(payload)
                payload["value"] = invalid
                self.assert_rejected(payload, (("value",), "type"))


COMMON = ("schema_version", "environment", "tenant_id", "site_id")
MAX_REV = 9007199254740991
BAD_DATE = "2026-02-30T00:00:00Z"
OFFSET = "2026-11-25T00:00:00+00:00"


class EnvelopeTests(CandidateTests):
    def test_envelope_fields(self):
        self.check_changes([
            ("schema_version", 2, "const"), ("environment", "other", "enum"),
            ("tenant_id", "Upper", "pattern"), ("site_id", "x" * 65, "maxLength"),
            ("site_id", 1, "type"), ("unknown", True, "additionalProperties"),
        ])
        for field in self.timestamps:
            self.check_changes([(field, BAD_DATE, "format"), (field, OFFSET, "pattern")])


class CommandSchemaTests(EnvelopeTests, unittest.TestCase):
    candidate = "command"
    required = COMMON + ("gateway_id", "command_id", "actor", "asset_id", "action", "value",
                         "policy_version", "control_epoch", "target_rev", "issued_at",
                         "expires_at", "priority")
    timestamps = ("issued_at", "expires_at")

    def test_target_and_control_metadata(self):
        self.check_changes([
            ("asset_id", "bad id", "pattern"), ("group_id", "group-1", None),
            ("group_id", [], "type"), ("actor", "a" * 129, "maxLength"),
            ("priority", "other", "enum"), ("action", "other", "enum"),
        ])
        for field in ("policy_version", "control_epoch", "target_rev"):
            self.check_changes([(field, 0, None), (field, MAX_REV, None),
                                (field, -1, "minimum"), (field, MAX_REV + 1, "maximum"),
                                (field, True, "type")])

    def test_action_value(self):
        self.check_changes([("value", 0, None), ("value", 100, None), ("value", True, "type")])
        power = dict(self.example, action="set_power", value=False)
        self.check_changes([("value", True, None), ("value", 1, "type")], power)
        for value, boundary in [(-1, "minimum"), (101, "maximum")]:
            with self.subTest(value=value):
                errors = list(self.validator.iter_errors(dict(self.example, value=value)))
                self.assertEqual([(tuple(e.path), e.validator) for e in errors], [(("value",), "oneOf")])
                self.assertIn((("value",), boundary),
                              [(tuple(e.absolute_path), e.validator) for e in errors[0].context])

    def test_emergency_approval(self):
        emergency = dict(self.example, priority="emergency", approval_ref="approval-1", reason="lab")
        with self.subTest(case="valid emergency"):
            self.assert_valid(emergency)
        for field in ("approval_ref", "reason"):
            with self.subTest(field=field):
                payload = deepcopy(emergency)
                del payload[field]
                self.assert_rejected(payload, ((), "required"))
        self.check_changes([("approval_ref", "Bad", "pattern"), ("reason", "x" * 257, "maxLength")],
                           emergency)


class AckSchemaTests(EnvelopeTests, unittest.TestCase):
    candidate = "ack"
    required = COMMON + ("gateway_id", "message_id", "command_id", "asset_id", "device_time",
                         "status", "evidence_source")
    timestamps = ("device_time",)

    def test_verified_evidence(self):
        self.check_changes([
            ("observed_value", False, None), ("observed_value", "55", "type"),
            ("evidence_source", "independent_measurement", None),
            ("evidence_source", "adapter", "enum"), ("evidence_source", "gateway_journal", "enum"),
            ("command_id", "Bad", "pattern"), ("status", "other", "enum"),
        ])
        with self.subTest(case="missing observation"):
            payload = deepcopy(self.example)
            del payload["observed_value"]
            self.assert_rejected(payload, ((), "required"))

    def test_status_and_reason(self):
        for status in ("acknowledged", "executed", "rejected", "expired", "failed", "unknown"):
            payload = dict(self.example, status=status, evidence_source="gateway_journal")
            del payload["observed_value"]
            if status in ("acknowledged", "executed"):
                with self.subTest(status=status):
                    self.assert_valid(payload)
            else:
                payload["reason"] = "example"
                with self.subTest(status=status, reason="present"):
                    self.assert_valid(payload)
                with self.subTest(status=status, reason="absent"):
                    del payload["reason"]
                    self.assert_rejected(payload, ((), "required"))


class ReceiptSchemaTests(EnvelopeTests, unittest.TestCase):
    candidate = "receipt"
    required = COMMON + ("gateway_id", "message_id", "received_time", "status")
    timestamps = ("received_time",)

    def test_quarantine_reason(self):
        payload = dict(self.example, status="quarantined", reason="sample")
        with self.subTest(case="valid quarantine"):
            self.assert_valid(payload)
        self.check_changes([("reason", "Bad", "pattern"), ("reason", 1, "type")], payload)
        with self.subTest(case="missing quarantine reason"):
            del payload["reason"]
            self.assert_rejected(payload, ((), "required"))

    def test_receipt_fields(self):
        self.check_changes([("status", "other", "enum"), ("message_id", "Bad", "pattern"),
                            ("received_time", 1, "type"), ("reason", "optional", None)])


class ManifestSchemaTests(EnvelopeTests, unittest.TestCase):
    candidate = "manifest"
    required = COMMON + ("manifest_id", "version", "player_ids", "files", "author", "approver",
                         "starts_at", "ends_at", "time_zone", "brightness_policy", "fallback_id",
                         "revocation_version")
    timestamps = ("starts_at", "ends_at")

    def test_publication_metadata(self):
        self.check_changes([
            ("version", 0, None), ("version", -1, "minimum"),
            ("revocation_version", MAX_REV, None), ("revocation_version", MAX_REV + 1, "maximum"),
            ("approver", "", "minLength"), ("author", "a" * 129, "maxLength"),
            ("time_zone", 1, "type"), ("brightness_policy", "Bad", "pattern"),
            ("fallback_id", "Bad", "pattern"),
        ])

    def test_collections(self):
        players = [f"player-{n}" for n in range(201)]
        files = self.example["files"] * 201
        self.check_changes([
            ("player_ids", [], "minItems"), ("player_ids", players[:200], None),
            ("player_ids", players, "maxItems"), ("player_ids", ["p", "p"], "uniqueItems"),
            ("files", [], "minItems"), ("files", files[:200], None), ("files", files, "maxItems"),
        ])
        with self.subTest(case="invalid player ID"):
            self.assert_rejected(dict(self.example, player_ids=["Bad"]), (("player_ids", 0), "pattern"))

    def test_file_fields(self):
        required = ("object_key", "sha256", "size_bytes", "media_type", "width_px", "height_px")
        self.assertCountEqual(self.schema["properties"]["files"]["items"]["required"], required)
        for field in required:
            with self.subTest(missing=field):
                payload = deepcopy(self.example)
                del payload["files"][0][field]
                self.assert_rejected(payload, (("files", 0), "required"))
        for field, value, keyword in [
            ("object_key", "x" * 257, "maxLength"), ("sha256", "G" * 64, "pattern"),
            ("sha256", "a" * 63, "pattern"), ("size_bytes", 0, "minimum"),
            ("size_bytes", MAX_REV + 1, "maximum"), ("media_type", "", "minLength"),
            ("width_px", 0, "minimum"), ("height_px", 1.5, "type"),
        ]:
            with self.subTest(field=field, keyword=keyword):
                payload = deepcopy(self.example)
                payload["files"][0][field] = value
                self.assert_rejected(payload, (("files", 0, field), keyword))
        payload = deepcopy(self.example)
        with self.subTest(case="extra file property"):
            payload["files"][0]["unknown"] = 1
            self.assert_rejected(payload, (("files", 0), "additionalProperties"))
