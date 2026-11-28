"""Bằng chứng host-side cho audit S2–S7 (không cần bo, không cần broker).

Mỗi test đặt tên một cách audit có thể fail: nạp master secret, thiếu CRC chunk,
lộ secret ở PROV SHOW, payload không qua jsonschema/verify_envelope, thiếu hợp
đồng S3/S5/S7 trong source. Chạy:

    python -m unittest tests.test_firmware_audit -v
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import importlib
import json
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
SRC = ROOT / "src"
for path in (TOOLS, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

MASTER = "audit-master-secret"
SITE = "SITE_01"
DTYPE = "light"
DEVICE = "LGT_NODE_001"
TOPIC = f"telemetry/v1/{SITE}/{DTYPE}/{DEVICE}"
KEY = hmac.new(
    MASTER.encode(), f"{SITE}/{DTYPE}/{DEVICE}".encode(), hashlib.sha256
).digest()


def _load(name: str):
    return importlib.import_module(name)


def _args(tmp: Path):
    for name, body in (
        ("ca.pem", "-----BEGIN CERTIFICATE-----\nDUMMY\n"),
        ("cert.pem", "-----BEGIN CERTIFICATE-----\nDUMMY\n"),
        ("key.pem", "-----BEGIN PRIVATE KEY-----\nDUMMY\n"),
        ("secret", MASTER + "\n"),
        ("wifi", "DummyWifiPass\n"),
    ):
        (tmp / name).write_text(body, encoding="ascii")
    return [
        "--site", SITE,
        "--device-type", DTYPE,
        "--device-id", DEVICE,
        "--broker-host", "mqtt.dev.pccom.test",
        "--broker-port", "8885",
        "--wifi-ssid", "LAB_WIFI",
        "--wifi-pass-file", str(tmp / "wifi"),
        "--ca-pem", str(tmp / "ca.pem"),
        "--cert-pem", str(tmp / "cert.pem"),
        "--key-pem", str(tmp / "key.pem"),
        "--signing-secret-file", str(tmp / "secret"),
    ]


class ProvisionHostDerivationTests(unittest.TestCase):
    """S2: master secret chỉ tồn tại trên host, thiết bị nhận device key."""

    def test_frame_carries_derived_device_key_and_not_master(self) -> None:
        tool = _load("provision")
        with tempfile.TemporaryDirectory() as directory:
            args = tool.parse_args(_args(Path(directory)) + ["--out", "frame.bin"])
            frame, tlv, _ = tool.build_frame(args)
        fields = tool.parse_frame(frame)
        self.assertEqual(fields[9], KEY)
        self.assertEqual(len(fields[9]), 32)
        self.assertNotIn(MASTER.encode(), tlv)
        self.assertNotIn(MASTER.encode(), base64.b64decode(frame.split(b",")[0][6:]))

    def test_chunks_have_per_chunk_crc_and_total_crc(self) -> None:
        tool = _load("provision")
        with tempfile.TemporaryDirectory() as directory:
            args = tool.parse_args(_args(Path(directory)) + ["--out", "frame.bin"])
            full, tlv, total_crc = tool.build_frame(args)
            chunks = tool.chunk_frame(full, max_bytes=1024)
        self.assertGreater(len(chunks), 1)
        rebuilt = bytearray()
        for chunk in chunks:
            parsed = tool.parse_chunk(chunk)
            if parsed["kind"] != "chunk":
                continue  # dòng tổng CRC không chứa dữ liệu
            prefix, crc_text = chunk.strip().rsplit(b",", 1)
            payload = prefix.split(b":", 2)[2]
            self.assertEqual(zlib.crc32(base64.b64decode(payload)) & 0xFFFFFFFF,
                             int(crc_text, 16))
            rebuilt += parsed["data"]
        self.assertEqual(bytes(rebuilt), tlv)
        self.assertEqual(tool.total_crc(chunks), total_crc)

    def test_corrupt_chunk_is_rejected(self) -> None:
        tool = _load("provision")
        with tempfile.TemporaryDirectory() as directory:
            args = tool.parse_args(_args(Path(directory)) + ["--out", "frame.bin"])
            chunks = tool.chunk_frame(tool.build_frame(args)[0], max_bytes=1024)
        broken = chunks[0].replace(b"PCCOM:", b"PCCOM!", 1)
        with self.assertRaises(tool.ProvisioningError):
            tool.parse_chunk(broken)

    def test_show_prints_only_lengths_and_fingerprint(self) -> None:
        env = os.environ.copy()
        env.pop("PCCOM_SIGNING_SECRET", None)
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            out = tmp / "frame.bin"
            command = [sys.executable, str(TOOLS / "provision.py"), "build"]
            command += _args(tmp) + ["--out", str(out)]
            subprocess.run(command, capture_output=True, env=env, check=True)
            result = subprocess.run(
                [sys.executable, str(TOOLS / "provision.py"), "show", "--in", str(out)],
                capture_output=True, env=env, check=True,
            )
            text = result.stdout.decode("utf-8", "replace")
            self.assertIn("fingerprint", text)
            self.assertIn("tlv_bytes", text)
            self.assertNotIn(MASTER, text)
            self.assertNotIn(base64.b64encode(KEY).decode(), text)
            self.assertNotIn(MASTER, result.stderr.decode("utf-8", "replace"))


class PayloadContractTests(unittest.TestCase):
    """S4: payload mẫu sinh ra phải qua jsonschema và verify_envelope."""

    def test_sample_payload_passes_jsonschema_and_envelope(self) -> None:
        jsonschema = importlib.import_module("jsonschema")
        sample = _load("firmware_payload_sample")
        headers = _load("iot_protocol.headers")
        payload, props = sample.sample_message(sequence=7, ts_ms=1794660440618)
        schema = json.loads((ROOT / "docs/data_contracts/schemas.json").read_text(encoding="utf-8"))
        jsonschema.validate(payload, schema)
        text = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        cid, ts, _ = headers.verify_envelope(KEY, TOPIC, text, props)
        self.assertEqual(cid, payload["message_id"])
        self.assertEqual(ts, 1794660440618)

    def test_signature_from_sample_matches_firmware_vector_scheme(self) -> None:
        sample = _load("firmware_payload_sample")
        payload, props = sample.sample_message(sequence=7, ts_ms=1794660440618)
        text = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        canonical = f"v1\n{TOPIC}\n{payload['message_id']}\n{props['ts_ms']}\n{text}"
        expected = hmac.new(KEY, canonical.encode(), hashlib.sha256).hexdigest()
        self.assertEqual(props["signature"], expected)


class StaticContractTests(unittest.TestCase):
    """Các hợp đồng chỉ chứng minh được bằng build + so khớpsource (bo → CẦN BO)."""

    def _read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8", errors="replace")

    def test_s3_network_contract_present(self) -> None:
        source = self._read("src/firmware_esp32_idf/main/pccom_network.c")
        config = self._read("src/firmware_esp32_idf/main/pccom_config.h")
        self.assertIn("PCCOM_BACKOFF_MAX_MS", config)
        self.assertIn("PCCOM_BACKOFF_JITTER_MS", config)
        self.assertIn("certificate_common_name", source)
        self.assertNotIn("skip_cert_common_name_check", source)
        self.assertIn("set_user_property", source)
        self.assertIn("set_publish_property", source)
        self.assertIn("delete_user_property", source)
        self.assertIn("esp_mqtt_client_publish", source)

    def test_s3_wdt_timeout_exceeds_network_attempt(self) -> None:
        config = self._read("src/firmware_esp32_idf/main/pccom_config.h")
        import re
        wdt = int(re.search(r"#define\s+PCCOM_WDT_TIMEOUT_MS\s+(\d+)", config).group(1))
        net = int(re.search(r"#define\s+PCCOM_NET_ATTEMPT_TIMEOUT_MS\s+(\d+)", config).group(1))
        self.assertGreater(wdt, net)

    def test_s5_stack_highwater_logged_for_four_tasks(self) -> None:
        source = self._read("src/firmware_esp32_idf/main/main.c")
        text = source + self._read("src/firmware_esp32_idf/main/pccom_network.c")
        for handle in ("net_task", "ingest_task", "tele_task", "mqtt_task"):
            self.assertIn(f"uxTaskGetStackHighWaterMark({handle})", text)

    def test_s7_60s_stats_fields_present(self) -> None:
        source = self._read("src/firmware_esp32_idf/main/pccom_network.c")
        for field in ("free_heap", "min_free_heap", "largest_block",
                      "reconnect", "publish_fail", "queue_overflow",
                      "stack_min"):
            self.assertIn(field, source)

    def test_s6_negative_matrix_script_lists_all_cases(self) -> None:
        script = (TOOLS / "negative_mtls_matrix.py").read_text(encoding="utf-8")
        for case in ("wrong_ca", "cert_wrong_ca", "cn_not_in_acl",
                     "expired_cert", "missing_client_cert", "revoked_crl",
                     "connect_by_ip"):
            self.assertIn(case, script)


if __name__ == "__main__":
    unittest.main()
