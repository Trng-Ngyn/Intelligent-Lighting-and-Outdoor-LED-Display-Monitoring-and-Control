"""Kiểm chứng một bản tin telemetry đã ký từ firmware ESP-IDF (S5/S6).

Tool chạy trên host, không cần bo hay broker. Đầu vào là payload JSON **nguyên
văn** đã publish và User Properties MQTT 5 dạng JSON; tool đối soát topic,
schema Annex C, HMAC-SHA256 và (tuỳ chọn) tính liên tục của `sequence`.

Không in payload, PEM hay master secret ra stdout/stderr — chỉ in metadata an
toàn. Dùng để kiểm tra log capture trong lúc soak mà không làm lộ credential.

Ví dụ:

    python tools/verify_firmware_telemetry.py \\
        --payload-file captured.json --props-file props.json \\
        --topic telemetry/v1/SITE_01/light/LGT_NODE_001 \\
        --site SITE_01 --device-type light --device-id LGT_NODE_001 \\
        --secret-file C:/secure/master.secret --last-sequence 6
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import hmac
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from iot_protocol.signing import derive_device_key  # noqa: E402

SCHEMA_VERSION = "1.0.0"
METRIC_FIELDS = (
    "power_w",
    "energy_wh",
    "voltage_v",
    "current_a",
    "power_factor",
    "temperature_c",
    "ambient_lux",
)


class TelemetryError(Exception):
    """Bản tin không hợp lệ; message an toàn để in ra log."""


def _configure_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")


def verify_record(
    payload_text: str,
    *,
    topic: str,
    user_properties: dict[str, str],
    master_secret: str,
    site: str,
    device_type: str,
    device_id: str,
    last_sequence: Optional[int] = None,
) -> dict:
    """Kiểm chứng một bản tin; trả metadata an toàn hoặc nêu TelemetryError."""
    expected_topic = f"telemetry/v1/{site}/{device_type}/{device_id}"
    if topic != expected_topic:
        raise TelemetryError(f"topic {topic!r} không đúng {expected_topic!r}")

    for name in ("correlation_id", "ts_ms", "signature"):
        if name not in user_properties:
            raise TelemetryError(f"thiếu user property {name}")
    correlation_id = user_properties["correlation_id"]
    ts_ms = user_properties["ts_ms"]
    signature = user_properties["signature"]
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", correlation_id):
        raise TelemetryError("correlation_id không đúng định dạng UUID")
    if not ts_ms.isdigit():
        raise TelemetryError("ts_ms không phải số nguyên")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", signature):
        raise TelemetryError("signature không phải HMAC-SHA256 hex")

    try:
        payload = json.loads(payload_text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise TelemetryError("payload không phải JSON hợp lệ") from exc
    if not isinstance(payload, dict):
        raise TelemetryError("payload không phải object JSON")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise TelemetryError("schema_version không đúng 1.0.0")
    if payload.get("message_id") != correlation_id:
        raise TelemetryError("message_id khác correlation_id")
    if payload.get("asset_id") != device_id:
        raise TelemetryError(f"asset_id khác {device_id}")

    sequence = payload.get("sequence")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence <= 0:
        raise TelemetryError("sequence không phải số nguyên dương")
    if not isinstance(payload.get("source_time"), int):
        raise TelemetryError("source_time không phải số nguyên")
    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        raise TelemetryError("thiếu object metrics")
    for field in METRIC_FIELDS:
        value = metrics.get(field)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TelemetryError(f"metrics.{field} không phải số")
    if not isinstance(payload.get("relay_state"), bool):
        raise TelemetryError("relay_state không phải boolean")
    if not isinstance(payload.get("brightness_pct"), (int, float)):
        raise TelemetryError("brightness_pct không phải số")

    canonical = f"v1\n{topic}\n{correlation_id}\n{ts_ms}\n{payload_text}"
    key = derive_device_key(master_secret, site, device_type, device_id)
    expected = hmac.new(key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature.lower()):
        raise TelemetryError("signature không khớp canonical payload")

    if last_sequence is not None and sequence != last_sequence + 1:
        raise TelemetryError(
            f"sequence {sequence} không nối tiếp sau {last_sequence}"
        )

    return {
        "sequence": sequence,
        "message_id": correlation_id,
        "ts_ms": ts_ms,
    }


def _read_text(path: str, name: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise TelemetryError(f"không đọc được {name}: {path}") from exc


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Kiểm chứng telemetry firmware đã ký (chỉ đọc, không sửa gì).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--payload-file", required=True, help="file chứa payload JSON nguyên văn")
    parser.add_argument("--props-file", required=True, help="file JSON của User Properties MQTT 5")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--site", default="SITE_01")
    parser.add_argument("--device-type", default="light")
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--secret-file", help="file chứa HMAC master secret")
    parser.add_argument("--last-sequence", type=int, help="sequence bản tin trước đó (kiểm tra replay)")
    args = parser.parse_args(argv)
    if not args.secret_file and "PCCOM_SIGNING_SECRET" not in os.environ:
        args.secret = getpass.getpass("HMAC master secret (ẩn, không echo): ")
    elif args.secret_file:
        args.secret = _read_text(args.secret_file, "secret file").rstrip("\r\n")
    else:
        args.secret = os.environ["PCCOM_SIGNING_SECRET"]
    if not args.secret:
        raise TelemetryError("HMAC master secret rỗng")
    return args


def main(argv: Optional[list[str]] = None) -> int:
    _configure_utf8_streams()
    try:
        args = parse_args(argv)
        props = json.loads(_read_text(args.props_file, "props file"))
        if not isinstance(props, dict):
            raise TelemetryError("props file phải là object JSON")
        result = verify_record(
            _read_text(args.payload_file, "payload file"),
            topic=args.topic,
            user_properties=props,
            master_secret=args.secret,
            site=args.site,
            device_type=args.device_type,
            device_id=args.device_id,
            last_sequence=args.last_sequence,
        )
    except TelemetryError as exc:
        print(f"Lỗi telemetry: {exc}", file=sys.stderr)
        return 2
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"Lỗi telemetry: props file không đúng JSON: {exc}", file=sys.stderr)
        return 2
    print(
        f"OK seq={result['sequence']} message_id={result['message_id']} "
        f"ts_ms={result['ts_ms']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
