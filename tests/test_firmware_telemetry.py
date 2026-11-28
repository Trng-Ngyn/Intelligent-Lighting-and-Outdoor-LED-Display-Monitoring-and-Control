"""Host-side checks cho telemetry đã ký từ firmware ESP-IDF.

Chạy: python -m unittest tests.test_firmware_telemetry -v
Kỳ vọng signature được tính bằng hmac/hashlib trực tiếp trong test, không dùng
hàm của tool đang kiểm chứng.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import verify_firmware_telemetry as verifier  # noqa: E402

SECRET = "telemetry-dummy-secret"
TOPIC = "telemetry/v1/SITE_01/light/LGT_NODE_001"
CID = "00000000-0000-4000-8000-000000000007"
TS = "1794660440618"


def _payload(sequence: int = 7) -> dict:
    return {
        "schema_version": "1.0.0",
        "message_id": CID,
        "asset_id": "LGT_NODE_001",
        "sequence": sequence,
        "source_time": 1794660440,
        "metrics": {
            "power_w": 48.1,
            "energy_wh": 125.47,
            "voltage_v": 220.1,
            "current_a": 0.218,
            "power_factor": 0.95,
            "temperature_c": 47.0,
            "ambient_lux": 300.0,
        },
        "brightness_pct": 50,
        "relay_state": True,
        "quality": "GOOD",
    }


def _signed(
    payload: dict | None = None,
    *,
    topic: str = TOPIC,
    cid: str = CID,
    ts: str = TS,
) -> tuple[str, dict[str, str]]:
    text = json.dumps(payload or _payload(), separators=(",", ":"))
    canonical = f"v1\n{topic}\n{cid}\n{ts}\n{text}"
    key = hmac.new(SECRET.encode(), b"SITE_01/light/LGT_NODE_001", hashlib.sha256).digest()
    signature = hmac.new(key, canonical.encode(), hashlib.sha256).hexdigest()
    return text, {"correlation_id": cid, "ts_ms": ts, "signature": signature}


def _verify(text: str, props: dict[str, str], **overrides) -> dict:
    options = {
        "topic": TOPIC,
        "user_properties": props,
        "master_secret": SECRET,
        "site": "SITE_01",
        "device_type": "light",
        "device_id": "LGT_NODE_001",
    }
    options.update(overrides)
    return verifier.verify_record(text, **options)


class FirmwareTelemetryContractTests(unittest.TestCase):
    """Mỗi test đặt tên một bản tin sai mà S5/S6 phải bắt được."""

    def test_valid_record_returns_sequence_and_message_id(self) -> None:
        text, props = _signed()
        result = _verify(text, props)
        self.assertEqual(result["sequence"], 7)
        self.assertEqual(result["message_id"], CID)

    def test_tampered_payload_is_rejected(self) -> None:
        text, props = _signed()
        # Đổi giá trị sau khi đã ký: chữ ký cũ không còn khớp canonical mới.
        text = text.replace('"brightness_pct":50', '"brightness_pct":90')
        self.assertIn('"brightness_pct":90', text)
        with self.assertRaisesRegex(verifier.TelemetryError, "signature"):
            _verify(text, props)

    def test_missing_correlation_property_is_rejected(self) -> None:
        text, props = _signed()
        del props["correlation_id"]
        with self.assertRaisesRegex(verifier.TelemetryError, "correlation_id"):
            _verify(text, props)

    def test_wrong_asset_id_is_rejected(self) -> None:
        payload = _payload()
        payload["asset_id"] = "LGT_NODE_999"
        text, props = _signed(payload)
        with self.assertRaisesRegex(verifier.TelemetryError, "asset_id"):
            _verify(text, props)

    def test_sequence_gap_is_rejected_when_last_sequence_given(self) -> None:
        text, props = _signed()
        with self.assertRaisesRegex(verifier.TelemetryError, "sequence"):
            _verify(text, props, last_sequence=5)

    def test_wrong_topic_is_rejected(self) -> None:
        wrong_topic = "telemetry/v1/SITE_02/light/LGT_NODE_001"
        text, props = _signed(topic=wrong_topic)
        with self.assertRaisesRegex(verifier.TelemetryError, "topic"):
            _verify(text, props, topic=wrong_topic)

    def test_cli_does_not_print_secret(self) -> None:
        env = os.environ.copy()
        env.pop("PCCOM_SIGNING_SECRET", None)
        text, props = _signed()
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            (tmp / "payload.json").write_text(text, encoding="utf-8")
            (tmp / "props.json").write_text(json.dumps(props), encoding="utf-8")
            (tmp / "secret").write_text(SECRET, encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(TOOLS / "verify_firmware_telemetry.py"),
                    "--payload-file", str(tmp / "payload.json"),
                    "--props-file", str(tmp / "props.json"),
                    "--secret-file", str(tmp / "secret"),
                    "--topic", TOPIC,
                    "--site", "SITE_01",
                    "--device-type", "light",
                    "--device-id", "LGT_NODE_001",
                ],
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
            self.assertNotIn(SECRET.encode(), result.stdout)
            self.assertNotIn(SECRET.encode(), result.stderr)


if __name__ == "__main__":
    unittest.main()
