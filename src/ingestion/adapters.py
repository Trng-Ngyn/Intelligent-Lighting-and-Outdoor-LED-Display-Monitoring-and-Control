"""Explicit, registry-bound adapters into the approved Draft-07 contract."""

from datetime import datetime, timedelta, timezone
import json
import math
from uuid import UUID, uuid5


UNITS = {
    "power_w": "W", "energy_interval_wh": "Wh", "energy_register_wh": "Wh",
    "voltage_v": "V", "current_a": "A", "power_factor": "1",
    "illuminance_lx": "lx", "temperature_c": "°C", "dimming_pct": "%",
    "brightness_pct": "%", "heartbeat": "1", "is_on": "1",
    "runtime_s": "s", "driver_fault_code": "1",
}
ALIASES = {"ambient_lux": "illuminance_lx", "energy_wh": "energy_register_wh"}
QUALITIES = {
    "GOOD": "measured", "ESTIMATED": "estimated", "DEGRADED": "invalid",
    "measured": "measured", "estimated": "estimated", "unavailable": "unavailable",
    "missing": "unavailable", "invalid": "invalid", "stuck": "stuck",
}


def iso_time(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if not math.isfinite(value):
            raise ValueError("Non-finite source timestamp")
        value = datetime.fromtimestamp(value, timezone.utc)
    elif isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError("Missing source timestamp")
    if value.tzinfo is None:
        raise ValueError("A timezone is required for source_time")
    return value.astimezone(timezone.utc)


def stamp(value):
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


class TopicAdapter:
    def __init__(self, routes=(), enforce=False):
        self.routes = {}
        self.enforce = enforce
        self.replace(routes)

    def replace(self, routes):
        self.routes = {
            (row["field_site"], row["device_type"], row["device_code"]): dict(row)
            for row in routes
        }

    def normalize(self, topic, raw, received):
        if not isinstance(raw, dict):
            raise ValueError("Telemetry must be a JSON object")
        parts = topic.split("/")
        contract = "native"
        envelope = None
        if len(parts) == 5 and parts[:2] == ["telemetry", "v1"]:
            key = tuple(parts[2:])
        elif len(parts) == 5 and parts[:2] == ["pccom", "lighting"] and parts[4] == "telemetry":
            key = (parts[2], "light", parts[3])
            contract = "legacy"
        elif len(parts) == 6 and parts[:2] == ["pccom", "v1"] and parts[5] == "telemetry":
            envelope = raw
            key = (str(raw.get("source_site_id", "")),
                   str(raw.get("device_type", "")), str(raw.get("device_id", raw.get("asset_id", ""))))
            if key not in self.routes:
                matches = [
                    k for k, route in self.routes.items()
                    if (route["tenant_code"], route["cloud_site"], route["gateway_code"]) == tuple(parts[2:5])
                    and route["device_code"] == str(raw.get("device_id", raw.get("asset_id", "")))
                ]
                if len(matches) != 1:
                    raise ValueError("Northbound identity has no unique registered binding")
                key = matches[0]
            contract = "northbound"
        else:
            raise ValueError("Unsupported telemetry topic")
        route = self.routes.get(key)
        if route is None:
            if raw.get("message_type") in ("telemetry.lighting", "telemetry.led") and not self.enforce:
                return raw, {"source_contract": "native"}
            raise ValueError("Device/topic is not registered: " + "/".join(key))
        if envelope is not None:
            if (route["tenant_code"], route["cloud_site"], route["gateway_code"]) != tuple(parts[2:5]):
                raise ValueError("Northbound topic does not match the device binding")
            raw = envelope.get("data", envelope)
            if not isinstance(raw, dict):
                raise ValueError("Northbound data must be an object")
        expected_kind = "lighting" if route["kind"] == "lighting" else "led"
        identity = {name: str(route[name]) for name in ("tenant_id", "site_id", "asset_id", "device_id")}
        if raw.get("message_type") in ("telemetry.lighting", "telemetry.led"):
            for name, value in identity.items():
                if str(raw.get(name)) != value:
                    raise ValueError("Payload identity does not match the registered topic: " + name)
            if raw["message_type"] != "telemetry." + expected_kind:
                raise ValueError("Telemetry kind does not match the registered asset")
            return raw, {"source_contract": "native"}
        if raw.get("asset_id", route["device_code"]) not in (route["device_code"], identity["asset_id"]):
            raise ValueError("Legacy asset_id does not match the registered topic")

        source = iso_time(raw.get("source_time", envelope.get("source_time") if envelope else None))
        sequence = raw.get("sequence", envelope.get("sequence") if envelope else None)
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0:
            raise ValueError("A non-negative device sequence is required")
        original_id = raw.get("message_id")
        if original_id is None:
            raise ValueError("Source message_id is required for replay reconciliation")
        try:
            message_id = str(UUID(str(original_id)))
        except (ValueError, TypeError):
            message_id = str(uuid5(UUID(identity["asset_id"]), str(original_id)))
        quality = QUALITIES.get(str(raw.get("quality", "GOOD")))
        if quality is None:
            raise ValueError("Unrecognized source quality")
        source_metrics = raw.get("metrics", {})
        if "metric" in raw and "value" in raw:
            source_metrics = {raw["metric"]: {"value": raw["value"], "unit": raw.get("unit"),
                                             "quality": raw.get("quality")}}
        if not isinstance(source_metrics, dict):
            raise ValueError("metrics must be an object")
        source_metrics = dict(source_metrics)
        for name in ("brightness_pct", "is_on", "driver_fault_code"):
            if name in raw:
                source_metrics[name] = raw[name]
        metrics = {}
        for name, value in source_metrics.items():
            name = ALIASES.get(name, name)
            if name == "brightness_pct" and expected_kind == "lighting":
                name = "dimming_pct"
            if name not in UNITS:
                continue
            if isinstance(value, dict):
                q = QUALITIES.get(str(value.get("quality", raw.get("quality", "GOOD"))))
                unit, value = value.get("unit", UNITS[name]), value.get("value")
            else:
                q, unit = quality, UNITS[name]
            if q is None:
                raise ValueError("Unrecognized metric quality")
            if q in ("invalid", "unavailable", "stuck"):
                value = None
            metrics[name] = {"value": value, "unit": unit, "quality": q}
        metrics.setdefault("power_w", {"value": None, "unit": "W", "quality": "unavailable"})
        clock = raw.get("clock_quality", "uncertain")
        if "clock_quality" not in raw and route.get("trust_legacy_clock", False):
            if datetime(2020, 1, 1, tzinfo=timezone.utc) <= source <= received + timedelta(seconds=60):
                clock = "synced"
        firmware = str(raw.get("firmware", route["firmware"])).removeprefix("v")
        result = {
            "schema_version": 1, "message_type": "telemetry." + expected_kind,
            **identity, "message_id": message_id, "source_time": stamp(source),
            "received_time": stamp(received), "sequence": sequence,
            "firmware": firmware, "clock_quality": clock, "metrics": metrics,
        }
        metadata = {"source_contract": contract, "source_message_id": str(original_id)}
        if "energy_interval_wh" in metrics and metrics["energy_interval_wh"]["value"] is not None:
            result["energy_interval_start"] = stamp(iso_time(raw.get("energy_interval_start")))
        if "energy_register_wh" in metrics and metrics["energy_register_wh"]["value"] is not None:
            epoch = raw.get("counter_epoch", raw.get("boot_id", "legacy-inferred"))
            try:
                result["counter_epoch"] = str(UUID(str(epoch)))
            except ValueError:
                result["counter_epoch"] = str(uuid5(UUID(identity["asset_id"]), str(epoch)))
            metadata["inferred_counter_epoch"] = "counter_epoch" not in raw and "boot_id" not in raw
        # The original source is retained for quality/reconciliation, never used as SQL.
        metadata["source_payload"] = json.loads(json.dumps(raw, allow_nan=False))
        return result, metadata
