"""Ma trận tiêu cực mTLS cho lab broker (S6).

Mỗi ca đều phải bị từ chối, không được có bản tin nào đến ACL. Tool chỉ in
những dòng chứa mã lỗi mong đợi — không in PEM, private key hay secret.

    python tools/negative_mtls_matrix.py --list
    python tools/negative_mtls_matrix.py --all
    python tools/negative_mtls_matrix.py --case cert_wrong_ca

Ca `expired_cert` cần fixture hết hạn; nếu chưa có, tool tự sinh bằng openssl
(ký bởi field CA lab, ghi vào generated/test-clients — thư mục bị ignore).
Nếu openssl không hỗ trợ -not_before/-not_after, ca đó được báo CẦN FIXTURE.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ["docker", "compose", "--env-file", "compose.env",
           "-f", "docker-compose.lab.yml", "--profile", "test",
           "run", "--rm", "mqtt-tools"]

# Broker dùng MỘT server cert do server CA ký cho cả 3 listener. Client phải
# tin /clients/server-ca.crt. /pki/field-ca.crt và /pki/device-ca.crt là CA
# của CLIENT cert -> dùng làm CA sai trong ca wrong_ca.
SERVER_CA = "/clients/server-ca.crt"
WRONG_CA = "/pki/field-ca.crt"
GOOD_CERT = "/clients/dev_SITE_01_LGT_NODE_001.crt"
GOOD_KEY = "/clients/dev_SITE_01_LGT_NODE_001.key"

CASES = [
    {
        "name": "wrong_ca",
        "purpose": "client không tin CA ký cert broker -> handshake thất bại",
        "kind": "pub",
        "argv": ["-p", "8885", "--cafile", WRONG_CA,
                 "--cert", GOOD_CERT, "--key", GOOD_KEY,
                 "-t", "telemetry/v1/SITE_01/light/LGT_NODE_001"],
        "expect": ["certificate verify failed", "unknown ca", "tlsv1 alert",
                   "ssl handshake failure", "connection was lost"],
    },
    {
        "name": "cert_wrong_ca",
        "purpose": "client cert ký bởi CA lạ -> broker từ chối",
        "kind": "pub",
        "argv": ["-p", "8885", "--cafile", SERVER_CA,
                 "--cert", "/clients/unknown.crt", "--key", "/clients/unknown.key",
                 "-t", "telemetry/v1/SITE_01/light/LGT_NODE_001"],
        "expect": ["unknown ca", "tlsv1 alert", "connection was lost"],
    },
    {
        "name": "cn_not_in_acl",
        "purpose": "identity đúng nhưng topic ngoài ACL -> PUBACK bị từ chối",
        "kind": "pub",
        "argv": ["-p", "8885", "--cafile", SERVER_CA,
                 "--cert", GOOD_CERT, "--key", GOOD_KEY,
                 "-t", "status/v1/SITE_02/light/LGT_NODE_001"],
        "expect": ["not authorized", "rc:135"],
    },
    {
        "name": "expired_cert",
        "purpose": "client cert hết hạn -> broker từ chối",
        "kind": "pub",
        "argv": ["-p", "8885", "--cafile", SERVER_CA,
                 "--cert", "/clients/expired.crt", "--key", "/clients/expired.key",
                 "-t", "telemetry/v1/SITE_01/light/LGT_NODE_001"],
        "expect": ["certificate has expired", "certificate expired",
                   "tlsv1 alert", "connection was lost"],
        "fixture": "expired",
    },
    {
        "name": "missing_client_cert",
        "purpose": "listener require_certificate true -> handshake thất bại",
        "kind": "pub",
        "argv": ["-p", "8885", "--cafile", SERVER_CA,
                 "-t", "telemetry/v1/SITE_01/light/LGT_NODE_001"],
        "expect": ["certificate required", "ssl handshake failure",
                   "tlsv1 alert", "connection was lost"],
    },
    {
        "name": "revoked_crl",
        "purpose": "client cert nằm trong CRL của listener 8883 -> từ chối",
        "kind": "pub",
        "argv": ["-p", "8883", "--cafile", SERVER_CA,
                 "--cert", "/clients/revoked.crt", "--key", "/clients/revoked.key",
                 "-t", "telemetry/v1/SITE_01/light/LGT_NODE_001"],
        "expect": ["certificate revoked", "tlsv1 alert", "connection was lost"],
    },
    {
        "name": "connect_by_ip",
        "purpose": "nối bằng IP nhưng ép verify hostname khác -> phải báo sai CN",
        "kind": "openssl",
        "argv": ["-connect", "127.0.0.1:8885", "-tls1_3",
                 "-CAfile", str(ROOT / "generated/test-clients/server-ca.crt"),
                 "-cert", str(ROOT / "generated/test-clients/dev_SITE_01_LGT_NODE_001.crt"),
                 "-key", str(ROOT / "generated/test-clients/dev_SITE_01_LGT_NODE_001.key"),
                 "-verify_hostname", "wrong.example.test", "-brief"],
        "expect": ["hostname mismatch", "verification error", "verification failed"],
    },
    {
        "name": "positive_control",
        "purpose": "đối chứng: cert/CA/topic đúng phải được CONNACK 0 + PUBACK RC:16",
        "kind": "pub",
        "argv": ["-p", "8885", "--cafile", SERVER_CA,
                 "--cert", GOOD_CERT, "--key", GOOD_KEY,
                 "-t", "telemetry/v1/SITE_01/light/LGT_NODE_001"],
        "expect": ["received connack (0)", "received puback"],
        "must_succeed": True,
    },
]

CASES_BY_NAME = {case["name"]: case for case in CASES}


def _openssl() -> str:
    local = Path(r"C:\Program Files\Git\usr\bin\openssl.exe")
    return str(local) if local.exists() else "openssl"


def ensure_expired_fixture() -> bool:
    directory = ROOT / "generated" / "test-clients"
    cert = directory / "expired.crt"
    key = directory / "expired.key"
    if cert.exists() and key.exists():
        return True
    openssl = _openssl()
    csr = directory / "expired.csr"
    try:
        subprocess.run(
            [openssl, "req", "-new", "-newkey", "rsa:2048", "-nodes",
             "-keyout", str(key), "-out", str(csr), "-subj", "/CN=expired-node"],
            check=True, capture_output=True, timeout=120,
        )
        subprocess.run(
            [openssl, "x509", "-req", "-in", str(csr),
             "-CA", str(ROOT / "generated/ca/field/ca.crt"),
             "-CAkey", str(ROOT / "generated/ca/field/ca.key"),
             "-set_serial", "0x1007",
             "-not_before", "20200101000000Z", "-not_after", "20200102000000Z",
             "-out", str(cert)],
            check=True, capture_output=True, timeout=120,
        )
        return True
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False
    finally:
        csr.unlink(missing_ok=True)


def command_for(case: dict) -> list[str]:
    if case["kind"] == "pub":
        return COMPOSE + [
            "mosquitto_pub", "-h", "mqtt.dev.pccom.test", "-V", "mqttv5", "-d",
            *case["argv"], "-m", "matrix-negative", "-q", "1",
        ]
    return [_openssl(), "s_client", *case["argv"]]


def _safe_lines(text: str, needles: list[str]) -> list[str]:
    """Chỉ trả dòng có mã lỗi/kết quả mong đợi, đã cắt ngắn."""
    kept = []
    for raw in text.splitlines():
        line = raw.strip()
        lowered = line.lower()
        if "-----begin " in lowered or "private key" in lowered:
            continue
        if any(needle in lowered for needle in needles):
            kept.append(line[:240])
    return kept[:6]


def run_case(case: dict, *, raw: bool = False) -> tuple[str, str, list[str]]:
    if case.get("fixture") == "expired" and not ensure_expired_fixture():
        return "CẦN FIXTURE", "openssl không tạo được cert hết hạn (-not_before/-not_after)", []
    try:
        result = subprocess.run(
            command_for(case), cwd=ROOT, capture_output=True, text=True,
            errors="replace", timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "FAIL", f"không chạy được lệnh: {exc}", []
    combined = result.stdout + "\n" + result.stderr
    lowered = combined.lower()
    matched = [needle for needle in case["expect"] if needle in lowered]
    must_succeed = case.get("must_succeed", False)
    if case["kind"] == "openssl":
        # s_client -brief trả exit=0 dù verify lỗi; bằng chứng là dòng verify.
        ok = bool(matched)
    elif must_succeed:
        ok = bool(matched) and result.returncode == 0
    else:
        # mosquitto_pub trả exit=0 ngay cả khi PUBACK bị từ chối (RC:135),
        # nên bằng chứng là mã lỗi trong output, không phải exit code.
        ok = bool(matched)
    evidence = _safe_lines(combined, case["expect"])
    if not evidence:
        evidence = [f"exit={result.returncode} (không thấy mã mong đợi)"]
    raw_lines = [line.strip()[:200] for line in combined.splitlines()
                 if line.strip() and "-----begin " not in line.lower()
                 and "private key" not in line.lower()][-12:] if raw else []
    return ("PASS" if ok else "FAIL"), "; ".join(evidence), raw_lines


def main(argv: Optional[list[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--all", action="store_true", help="chạy toàn bộ ma trận")
    target.add_argument("--case", choices=list(CASES_BY_NAME))
    target.add_argument("--list", action="store_true", help="chỉ liệt kê ca")
    parser.add_argument("--raw", action="store_true",
                        help="in thêm output thô đã lọc PEM/key để debug")
    args = parser.parse_args(argv)

    if args.list:
        for case in CASES:
            print(f"{case['name']:<20} {case['purpose']}")
        return 0

    selected = CASES if args.all else [CASES_BY_NAME[args.case]]
    failed = 0
    for case in selected:
        status, evidence, raw = run_case(case, raw=args.raw)
        if status != "PASS":
            failed += 1
        print(f"{status:<13} {case['name']:<20} {evidence}")
        if args.raw and raw:
            print("    RAW: " + " | ".join(raw))
    print(f"TỔNG: {len(selected) - failed}/{len(selected)} ca đúng kỳ vọng")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
