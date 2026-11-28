"""Host-side checks cho khung provisioning của firmware ESP-IDF.

Chạy: python -m unittest tests.test_firmware_provisioning -v
Không cần bo, không cần broker; credential trong test là giá trị giả.
"""

from __future__ import annotations

import argparse
import base64
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import provision_esp32  # noqa: E402

SECRET = b"S4-dummy-master-secret-123"
WIFI_PASS = b"DummyWifiPass"


def _args(tmp: Path) -> argparse.Namespace:
    (tmp / "ca.pem").write_text("-----BEGIN CERTIFICATE-----\nDUMMY\n", encoding="ascii")
    (tmp / "cert.pem").write_text("-----BEGIN CERTIFICATE-----\nDUMMY\n", encoding="ascii")
    (tmp / "key.pem").write_text("-----BEGIN PRIVATE KEY-----\nDUMMY\n", encoding="ascii")
    (tmp / "secret").write_bytes(SECRET + b"\n")
    (tmp / "wifi").write_bytes(WIFI_PASS + b"\n")
    return argparse.Namespace(
        site="SITE_01",
        device_type="light",
        device_id="LGT_NODE_001",
        client_id="LGT_NODE_001",
        broker_host="mqtt.example.test",
        broker_port=8883,
        wifi_ssid="LAB_WIFI",
        wifi_pass_file=str(tmp / "wifi"),
        ca_pem=str(tmp / "ca.pem"),
        cert_pem=str(tmp / "cert.pem"),
        key_pem=str(tmp / "key.pem"),
        signing_secret_file=str(tmp / "secret"),
        out=None,
        port=None,
    )


def _frame(tlv: bytes) -> bytes:
    crc = zlib.crc32(tlv) & 0xFFFFFFFF
    return b"PCCOM:" + base64.b64encode(tlv) + b"," + f"{crc:08x}".encode() + b"\n"


def _tlv(tag: int, value: bytes) -> bytes:
    return bytes([tag]) + struct.pack(">H", len(value)) + value


class FirmwareProvisioningFrameTests(unittest.TestCase):
    """Mỗi test đặt tên một cách khung bị hỏng mà firmware sẽ từ chối."""

    def test_parse_frame_roundtrip_returns_all_tags(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            frame, _, _ = provision_esp32.build_frame(_args(Path(directory)))
            parsed = provision_esp32.parse_frame(frame)
            self.assertEqual(list(parsed), list(range(13)))
            self.assertEqual(parsed[0], b"\x01")
            self.assertEqual(parsed[3], b"LGT_NODE_001")
            self.assertEqual(parsed[9], SECRET)

    def test_parse_frame_rejects_version_not_first(self) -> None:
        tlv = _tlv(3, b"LGT_NODE_001") + _tlv(0, b"\x01")
        with self.assertRaisesRegex(provision_esp32.ProvisioningError, "BAD_TLV"):
            provision_esp32.parse_frame(_frame(tlv))

    def test_parse_frame_rejects_wrong_version_value(self) -> None:
        tlv = _tlv(0, b"\x02") + _tlv(3, b"LGT_NODE_001")
        with self.assertRaisesRegex(provision_esp32.ProvisioningError, "BAD_TLV"):
            provision_esp32.parse_frame(_frame(tlv))

    def test_parse_frame_rejects_crc_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            frame, _, _ = provision_esp32.build_frame(_args(Path(directory)))
        prefix, crc = frame.strip().rsplit(b",", 1)
        bad_crc = b"0" * 8 if crc != b"0" * 8 else b"1" * 8
        with self.assertRaisesRegex(provision_esp32.ProvisioningError, "CRC_MISMATCH"):
            provision_esp32.parse_frame(prefix + b"," + bad_crc + b"\n")

    def test_parse_frame_rejects_bad_base64(self) -> None:
        frame = b"PCCOM:%%%,7249888a\n"
        with self.assertRaisesRegex(provision_esp32.ProvisioningError, "BAD_BASE64"):
            provision_esp32.parse_frame(frame)

    def test_cli_never_prints_secret(self) -> None:
        env = os.environ.copy()
        for key in ("PCCOM_SIGNING_SECRET", "PCCOM_WIFI_PASS"):
            env.pop(key, None)
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            args = _args(tmp)
            out = tmp / "frame.pccom-frame"
            command = [
                sys.executable,
                str(TOOLS / "provision_esp32.py"),
                "--device-id", args.device_id,
                "--broker-host", args.broker_host,
                "--broker-port", str(args.broker_port),
                "--wifi-ssid", args.wifi_ssid,
                "--ca-pem", args.ca_pem,
                "--cert-pem", args.cert_pem,
                "--key-pem", args.key_pem,
                "--signing-secret-file", args.signing_secret_file,
                "--wifi-pass-file", args.wifi_pass_file,
                "--out", str(out),
            ]
            result = subprocess.run(command, capture_output=True, env=env, check=False)
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
            self.assertNotIn(SECRET, result.stdout)
            self.assertNotIn(SECRET, result.stderr)
            self.assertNotIn(WIFI_PASS, result.stdout)
            self.assertNotIn(WIFI_PASS, result.stderr)
            self.assertEqual(provision_esp32.parse_frame(out.read_bytes())[9], SECRET)


if __name__ == "__main__":
    unittest.main()
