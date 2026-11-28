"""Sinh khung provisioning UART1 cho firmware ESP32-WROOM-32 (ESP-IDF S3/S4).

Khung gửi cho firmware:

    PCCOM:<base64(TLV)>,<crc32hex>\\n
    TLV = tag(1 byte) | length(2 byte big-endian) | value

TLV đầu tiên phải là version: tag=0, len=1, value=1 (PCCOM_PROVISION_VERSION).
CRC32-IEEE (poly 0xEDB88320) tính trên **bytes TLV sau khi decode**, ghi thành
8 chữ số hex. Khớp `main/pccom_provision.c`.

BẢO MẬT: base64 không phải mã hóa. Khung chứa CA/key/secret ở dạng có thể
decode được, nên công cụ **không bao giờ in khung ra stdout**. Bắt buộc chọn
`--out <file>` (khuyến nghị, file nằm ngoài repo) hoặc `--port <serial>` để gửi
trực tiếp cho bo. Mật khẩu WiFi và HMAC master secret chỉ đọc từ file, biến môi
trường hoặc prompt ẩn; không nhận qua đối số dòng lệnh để tròn lịch sử shell.

Ví dụ:

    python tools/provision_esp32.py \\
        --device-id LGT_NODE_001 --broker-host mqtt.example.test \\
        --broker-port 8883 --wifi-ssid LAB_WIFI \\
        --ca-pem generated/mqtt/ca.crt \\
        --cert-pem generated/mqtt/device.crt \\
        --key-pem generated/mqtt/device.key \\
        --signing-secret-file /secure/path/master.secret \\
        --wifi-pass-file /secure/path/wifi.pass \\
        --out C:/Temp/LGT_NODE_001.pccom-frame

Gửi thẳng qua UART1 (RX=GPIO16, TX=GPIO17, 115200 8N1):

    python tools/provision_esp32.py ... --port COM3
"""

from __future__ import annotations

import argparse
import base64
import binascii
import getpass
import os
import re
import struct
import sys
import zlib
from pathlib import Path
from typing import Optional

PROVISION_VERSION = 1
FRAME_PREFIX = b"PCCOM:"
UART_BAUD = 115200

TAG_VERSION = 0
TAG_SITE = 1
TAG_DEVICE_TYPE = 2
TAG_DEVICE_ID = 3
TAG_BROKER_HOST = 4
TAG_BROKER_PORT = 5
TAG_CA_PEM = 6
TAG_CLIENT_CERT = 7
TAG_CLIENT_KEY = 8
TAG_SIGNING_SECRET = 9
TAG_WIFI_SSID = 10
TAG_WIFI_PASS = 11
TAG_CLIENT_ID = 12

MAX_SEGMENT = 64
MAX_HOST = 128
MAX_SSID = 32
MAX_WIFI_PASS = 64
MAX_PEM = 4096
MAX_SECRET = 256

SEGMENT_RE = re.compile(r"^[A-Za-z0-9_-]+$")
HOST_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")


class ProvisioningError(Exception):
    """Lỗi input/khung/giao tiếp; message luôn an toàn để in ra log."""


def _configure_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")


def _tlv(tag: int, value: bytes) -> bytes:
    if len(value) > 0xFFFF:
        raise ProvisioningError(f"TLV tag={tag} dài hơn 65535 bytes")
    return bytes([tag]) + struct.pack(">H", len(value)) + value


def _segment(name: str, value: str, max_len: int = MAX_SEGMENT) -> bytes:
    data = value.encode("utf-8")
    if not data or len(data) > max_len or not SEGMENT_RE.fullmatch(value):
        raise ProvisioningError(
            f"{name} phải là 1-{max_len} ký tự [A-Za-z0-9_-], không được rỗng"
        )
    return data


def _host(value: str) -> bytes:
    data = value.encode("utf-8")
    if not data or len(data) > MAX_HOST or not HOST_RE.fullmatch(value):
        raise ProvisioningError(
            f"broker_host phải là 1-{MAX_HOST} ký tự hostname/IP hợp lệ"
        )
    return data


def _text(value: str, name: str, max_len: int) -> bytes:
    data = value.encode("utf-8")
    if not data or len(data) > max_len or b"\x00" in data:
        raise ProvisioningError(f"{name} phải có 1-{max_len} byte và không chứa NUL")
    return data


def _read_file(path: str, name: str, max_len: int) -> bytes:
    file_path = Path(path)
    if not file_path.is_file():
        raise ProvisioningError(f"không tìm thấy {name}: {file_path}")
    data = file_path.read_bytes()
    if not data or len(data) > max_len:
        raise ProvisioningError(f"{name} phải có 1-{max_len} byte")
    return data


def _read_secret(
    file_path: Optional[str], env_name: str, label: str, max_len: int
) -> bytes:
    """Đọc giá trị nhạy cảm; trailing newline được bỏ để khớp UTF-8 host."""
    if file_path:
        data = _read_file(file_path, label, max_len + 2)
    elif env_name in os.environ:
        data = os.environ[env_name].encode("utf-8")
    else:
        data = getpass.getpass(f"{label} (ẩn, không echo): ").encode("utf-8")
    data = data.rstrip(b"\r\n")
    if not data or len(data) > max_len:
        raise ProvisioningError(f"{label} phải có 1-{max_len} byte sau khi bỏ newline")
    return data


def build_frame(args: argparse.Namespace) -> tuple[bytes, int, int]:
    """Trả về (frame, tlv_len, crc32). Không giá trị trường nào được log."""
    site = _segment("site_id", args.site)
    device_type = _segment("device_type", args.device_type)
    device_id = _segment("device_id", args.device_id)
    client_id = _segment("client_id", args.client_id)
    host = _host(args.broker_host)
    if not 1 <= args.broker_port <= 65535:
        raise ProvisioningError("broker_port phải nằm trong 1..65535")
    port = struct.pack(">H", args.broker_port)
    ca_pem = _read_file(args.ca_pem, "CA PEM", MAX_PEM)
    cert_pem = _read_file(args.cert_pem, "client certificate PEM", MAX_PEM)
    key_pem = _read_file(args.key_pem, "client private key PEM", MAX_PEM)
    secret = _read_secret(
        args.signing_secret_file, "PCCOM_SIGNING_SECRET", "HMAC master secret",
        MAX_SECRET,
    )
    ssid = _text(args.wifi_ssid, "WiFi SSID", MAX_SSID)
    wifi_pass = _read_secret(
        args.wifi_pass_file, "PCCOM_WIFI_PASS", "WiFi password", MAX_WIFI_PASS
    )

    tlv = b"".join(
        [
            _tlv(TAG_VERSION, bytes([PROVISION_VERSION])),
            _tlv(TAG_SITE, site),
            _tlv(TAG_DEVICE_TYPE, device_type),
            _tlv(TAG_DEVICE_ID, device_id),
            _tlv(TAG_BROKER_HOST, host),
            _tlv(TAG_BROKER_PORT, port),
            _tlv(TAG_CA_PEM, ca_pem),
            _tlv(TAG_CLIENT_CERT, cert_pem),
            _tlv(TAG_CLIENT_KEY, key_pem),
            _tlv(TAG_SIGNING_SECRET, secret),
            _tlv(TAG_WIFI_SSID, ssid),
            _tlv(TAG_WIFI_PASS, wifi_pass),
            _tlv(TAG_CLIENT_ID, client_id),
        ]
    )
    crc = zlib.crc32(tlv) & 0xFFFFFFFF
    frame = (
        FRAME_PREFIX
        + base64.b64encode(tlv)
        + b","
        + f"{crc:08x}".encode("ascii")
        + b"\n"
    )
    return frame, len(tlv), crc


def parse_frame(frame: bytes) -> dict[int, bytes]:
    """Đọc lại khung do `build_frame` sinh, trả `{tag: value}`.

    Bắt chước trình tự kiểm tra của `pccom_provision.c`: prefix → base64 → CRC
    → TLV, trong đó TLV đầu tiên bắt buộc là version=1. Lỗi dùng cùng mã với
    firmware (`BAD_FRAME`, `BAD_BASE64`, `CRC_MISMATCH`, `BAD_TLV`) để test
    host-side có thể sinh khung tiêu cực cho S5. Không trả/error chứa secret.
    """
    line = frame.strip()
    if not line.startswith(FRAME_PREFIX):
        raise ProvisioningError("BAD_FRAME")
    rest = line[len(FRAME_PREFIX):]
    if b"," not in rest:
        raise ProvisioningError("BAD_FRAME")
    encoded, crc_text = rest.rsplit(b",", 1)
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ProvisioningError("BAD_BASE64") from exc
    if len(crc_text) != 8:
        raise ProvisioningError("BAD_FRAME")
    try:
        expected_crc = int(crc_text.decode("ascii"), 16)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ProvisioningError("BAD_FRAME") from exc
    if zlib.crc32(decoded) & 0xFFFFFFFF != expected_crc:
        raise ProvisioningError("CRC_MISMATCH")

    fields: dict[int, bytes] = {}
    offset = 0
    while offset < len(decoded):
        if len(decoded) - offset < 3:
            raise ProvisioningError("BAD_TLV")
        tag = decoded[offset]
        length = struct.unpack(">H", decoded[offset + 1:offset + 3])[0]
        offset += 3
        if length > len(decoded) - offset:
            raise ProvisioningError("BAD_TLV")
        value = decoded[offset:offset + length]
        offset += length
        if not fields:
            if tag != TAG_VERSION or length != 1 or value != bytes([PROVISION_VERSION]):
                raise ProvisioningError("BAD_TLV")
        elif tag == TAG_VERSION:
            raise ProvisioningError("BAD_TLV")
        fields[tag] = value
    if not fields:
        raise ProvisioningError("BAD_TLV")
    return fields


def _write_file(frame: bytes, out_path: str) -> None:
    path = Path(out_path)
    if path.is_dir():
        raise ProvisioningError(f"--out phải là file, không phải thư mục: {path}")
    path.write_bytes(frame)
    try:
        os.chmod(path, 0o600)
    except (AttributeError, OSError):
        pass  # Windows không hỗ trợ mode POSIX; vẫn cảnh báo user ở summary.
    print(f"Đã ghi khung (nhạy cảm) vào {path} — không commit file này.")


def _send_serial(frame: bytes, port: str) -> None:
    try:
        import serial  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - phụ thuộc môi trường
        raise ProvisioningError(
            "cần pyserial để dùng --port: pip install pyserial"
        ) from exc

    try:
        with serial.Serial(port, UART_BAUD, timeout=5) as link:
            ready = link.readline().strip()
            if ready != b"+READY":
                raise ProvisioningError(
                    "bo chưa gửi +READY (sai cổng, sai baud hoặc đã có config)"
                )
            link.write(frame)
            reply = link.readline().strip().decode("ascii", errors="replace")
    except ProvisioningError:
        raise
    except Exception as exc:  # serial.SerialException và bạn bè
        raise ProvisioningError(f"lỗi UART {port}: {exc}") from exc

    if reply == "+ACK":
        print("Bo trả +ACK: đã lưu cấu hình vào NVS.")
    else:
        raise ProvisioningError(f"bo từ chối khung: {reply or 'không có phản hồi'}")


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tạo/gửi khung provisioning cho firmware ESP32 ESP-IDF (S3/S4).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--site", default="SITE_01", help="site_id")
    parser.add_argument(
        "--device-type", default="light",
        choices=["light", "led_display", "gateway"],
    )
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--client-id", help="MQTT client id / CN cert; mặc định = device-id")
    parser.add_argument("--broker-host", required=True)
    parser.add_argument("--broker-port", type=int, required=True)
    parser.add_argument("--wifi-ssid", default=os.environ.get("PCCOM_WIFI_SSID"))
    parser.add_argument("--wifi-pass-file", help="file chứa WiFi password (khuyến nghị)")
    parser.add_argument("--ca-pem", required=True, help="file CA PEM của broker")
    parser.add_argument("--cert-pem", required=True, help="file client certificate PEM")
    parser.add_argument("--key-pem", required=True, help="file client private key PEM")
    parser.add_argument(
        "--signing-secret-file", help="file chứa HMAC master secret (UTF-8)"
    )
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--out", help="ghi khung vào file (không in ra màn hình)")
    destination.add_argument("--port", help="gửi khung qua cổng serial, ví dụ COM3")
    args = parser.parse_args(argv)
    if not args.client_id:
        args.client_id = args.device_id
    if not args.wifi_ssid:
        parser.error("--wifi-ssid hoặc PCCOM_WIFI_SSID là bắt buộc")
    return args


def main(argv: Optional[list[str]] = None) -> int:
    _configure_utf8_streams()
    try:
        args = parse_args(argv)
        frame, tlv_len, crc = build_frame(args)
        # Chỉ in metadata an toàn; không in base64, PEM, key hay secret.
        print(
            f"-frame-meta site={args.site} type={args.device_type} "
            f"device={args.device_id} client={args.client_id} "
            f"broker={args.broker_host}:{args.broker_port} "
            f"version={PROVISION_VERSION} tlv_bytes={tlv_len} "
            f"frame_bytes={len(frame)} crc32={crc:08x}"
        )
        if args.out:
            _write_file(frame, args.out)
        else:
            _send_serial(frame, args.port)
        return 0
    except ProvisioningError as exc:
        print(f"Lỗi provisioning: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Đã hủy.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
