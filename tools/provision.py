"""Provisioning an toàn cho ESP32 W5: master secret CHỈ ở host.

Khác với `provision_esp32.py` (frame đơn, tag 9 là master secret — giữ lại chỉ
để tương thích audit), tool này:

- dẫn xuất `device_key = HMAC-SHA256(master_secret, site/type/device)` trên
  host bằng `src/iot_protocol/signing.py`, rồi gửi đúng 32 byte device key
  trong TLV tag 9. Firmware không bao giờ nhận/lưu master secret.
- chia khung thành chunk ≤1024 byte TLV, mỗi chunk có CRC32 riêng, và có một
  dòng tổng CRC32 để firmware đối chiếu trước khi parse TLV/ghi NVS.
- có lệnh `show` chỉ in độ dài + fingerprint (SHA256/16 hex), không in PEM,
  private key, device key hay master secret.

Cú pháp khung (mỗi dòng kết thúc bởi \\n):

    PCCOM:C<seq>/<total>:<base64(chunk)>,<crc32(chunk):08x>
    ...
    PCCOM:S<crc32(toàn bộ TLV):08x>

Vẫn chấp nhận frame đơn `PCCOM:<base64(TLV)>,<crc32>` của firmware cũ.

Ví dụ:

    python tools/provision.py build <common-args> --out C:/secure/frame.bin
    python tools/provision.py show --in C:/secure/frame.bin
    python tools/provision.py send <common-args> --port COMx
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import os
import struct
import sys
import zlib
from pathlib import Path
from typing import Optional

import provision_esp32 as legacy

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from iot_protocol.signing import derive_device_key  # noqa: E402

ProvisioningError = legacy.ProvisioningError
FRAME_PREFIX = legacy.FRAME_PREFIX
TAG_DEVICE_KEY = legacy.TAG_SIGNING_SECRET  # tag 9, giữ giá trị để tương thích
DEVICE_KEY_LEN = 32
DEFAULT_CHUNK_BYTES = 1024


def _configure_utf8_streams() -> None:
    legacy._configure_utf8_streams()


def _crc(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def _device_key(master: bytes, site: str, device_type: str, device_id: str) -> bytes:
    try:
        text = master.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProvisioningError("master secret phải là UTF-8") from exc
    key = derive_device_key(text, site, device_type, device_id)
    if len(key) != DEVICE_KEY_LEN:
        raise ProvisioningError("device key không đúng 32 byte")
    return key


def build_frame(args: argparse.Namespace, *, chunk_bytes: int = DEFAULT_CHUNK_BYTES):
    """Trả (frame đơn, TLV, crc tổng). Frame đơn dùng cho --out/--port cũ."""
    site = legacy._segment("site_id", args.site)
    device_type = legacy._segment("device_type", args.device_type)
    device_id = legacy._segment("device_id", args.device_id)
    client_id = legacy._segment("client_id", args.client_id)
    host = legacy._host(args.broker_host)
    if not 1 <= args.broker_port <= 65535:
        raise ProvisioningError("broker_port phải nằm trong 1..65535")
    master = legacy._read_secret(
        args.signing_secret_file, "PCCOM_SIGNING_SECRET", "HMAC master secret",
        legacy.MAX_SECRET,
    )
    key = _device_key(master, args.site, args.device_type, args.device_id)
    ca_pem = legacy._read_file(args.ca_pem, "CA PEM", legacy.MAX_PEM)
    cert_pem = legacy._read_file(args.cert_pem, "client certificate PEM", legacy.MAX_PEM)
    key_pem = legacy._read_file(args.key_pem, "client private key PEM", legacy.MAX_PEM)
    ssid = legacy._text(args.wifi_ssid, "WiFi SSID", legacy.MAX_SSID)
    wifi_pass = legacy._read_secret(
        args.wifi_pass_file, "PCCOM_WIFI_PASS", "WiFi password", legacy.MAX_WIFI_PASS
    )

    tlv = b"".join(
        [
            legacy._tlv(legacy.TAG_VERSION, bytes([legacy.PROVISION_VERSION])),
            legacy._tlv(legacy.TAG_SITE, site),
            legacy._tlv(legacy.TAG_DEVICE_TYPE, device_type),
            legacy._tlv(legacy.TAG_DEVICE_ID, device_id),
            legacy._tlv(legacy.TAG_BROKER_HOST, host),
            legacy._tlv(legacy.TAG_BROKER_PORT, struct.pack(">H", args.broker_port)),
            legacy._tlv(legacy.TAG_CA_PEM, ca_pem),
            legacy._tlv(legacy.TAG_CLIENT_CERT, cert_pem),
            legacy._tlv(legacy.TAG_CLIENT_KEY, key_pem),
            legacy._tlv(TAG_DEVICE_KEY, key),
            legacy._tlv(legacy.TAG_WIFI_SSID, ssid),
            legacy._tlv(legacy.TAG_WIFI_PASS, wifi_pass),
            legacy._tlv(legacy.TAG_CLIENT_ID, client_id),
        ]
    )
    crc = _crc(tlv)
    frame = (
        FRAME_PREFIX
        + base64.b64encode(tlv)
        + b","
        + f"{crc:08x}".encode("ascii")
        + b"\n"
    )
    return frame, tlv, crc


def parse_frame(frame: bytes) -> dict[int, bytes]:
    fields = legacy.parse_frame(frame)
    if TAG_DEVICE_KEY not in fields or len(fields[TAG_DEVICE_KEY]) != DEVICE_KEY_LEN:
        raise ProvisioningError("BAD_TLV: tag=9 phải là device key 32 byte")
    return fields


def chunk_frame(frame: bytes, max_bytes: int = DEFAULT_CHUNK_BYTES) -> list[bytes]:
    """Chia TLV thành các dòng `PCCOM:C..` + một dòng `PCCOM:S..` tổng CRC."""
    if max_bytes < 1 or max_bytes > 1024:
        raise ProvisioningError("chunk size phải nằm trong 1..1024")
    line = frame.strip()
    if not line.startswith(FRAME_PREFIX) or b"," not in line:
        raise ProvisioningError("BAD_FRAME")
    encoded, _crc_text = line[len(FRAME_PREFIX):].rsplit(b",", 1)
    try:
        tlv = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ProvisioningError("BAD_BASE64") from exc
    parts = [tlv[i:i + max_bytes] for i in range(0, len(tlv), max_bytes)]
    total = len(parts)
    lines = []
    for index, part in enumerate(parts, 1):
        lines.append(
            FRAME_PREFIX
            + f"C{index}/{total}:".encode("ascii")
            + base64.b64encode(part)
            + b","
            + f"{_crc(part):08x}".encode("ascii")
            + b"\n"
        )
    lines.append(FRAME_PREFIX + f"S{_crc(tlv):08x}".encode("ascii") + b"\n")
    return lines


def parse_chunk(line: bytes) -> dict:
    """Đọc một dòng chunk/tổng; message lỗi an toàn, không chứa dữ liệu."""
    text = line.strip()
    if not text.startswith(FRAME_PREFIX):
        raise ProvisioningError("BAD_FRAME")
    body = text[len(FRAME_PREFIX):]
    if body.startswith(b"S"):
        crc_text = body[1:]
        if len(crc_text) != 8:
            raise ProvisioningError("BAD_FRAME")
        try:
            return {"kind": "summary", "total_crc": int(crc_text, 16)}
        except ValueError as exc:
            raise ProvisioningError("BAD_FRAME") from exc
    if not body.startswith(b"C"):
        # Frame đơn: để firmware/tool legacy xử lý.
        legacy.parse_frame(text + b"\n")
        return {"kind": "single"}
    rest = body[1:]
    if b":" not in rest or b"," not in rest:
        raise ProvisioningError("BAD_FRAME")
    counters, crc_text = rest.rsplit(b",", 1)
    counter_text, encoded = counters.split(b":", 1)
    try:
        seq, total = (int(part) for part in counter_text.split(b"/", 1))
        expected_crc = int(crc_text, 16)
    except ValueError as exc:
        raise ProvisioningError("BAD_FRAME") from exc
    if not (1 <= seq <= total):
        raise ProvisioningError("BAD_FRAME")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ProvisioningError("BAD_BASE64") from exc
    if _crc(data) != expected_crc:
        raise ProvisioningError("CRC_MISMATCH")
    return {"kind": "chunk", "seq": seq, "total": total, "data": data}


def tlv_from_chunked(raw: bytes) -> bytes:
    """Trả TLV đã ghép lại để tính fingerprint khớp với lúc build."""
    parts = {}
    for line in raw.splitlines():
        parsed = parse_chunk(line)
        if parsed["kind"] == "chunk":
            parts[parsed["seq"]] = parsed["data"]
    if not parts or sorted(parts) != list(range(1, len(parts) + 1)):
        raise ProvisioningError("BAD_FRAME: thiếu/trùng chunk")
    return b"".join(parts[index] for index in sorted(parts))


def parse_chunked(raw: bytes) -> dict[int, bytes]:
    """Đọc file chunked (hoặc frame đơn), trả TLV fields đã kiểm chứng CRC."""
    lines = [line for line in raw.splitlines() if line.strip()]
    if not lines:
        raise ProvisioningError("BAD_FRAME")
    if len(lines) == 1 and lines[0].startswith(FRAME_PREFIX + b"C") is False:
        return parse_frame(raw)
    parts: dict[int, bytes] = {}
    summary = None
    for line in lines:
        parsed = parse_chunk(line)
        if parsed["kind"] == "chunk":
            if parsed["seq"] in parts:
                raise ProvisioningError("BAD_FRAME: chunk trùng seq")
            parts[parsed["seq"]] = parsed["data"]
        elif parsed["kind"] == "summary":
            summary = parsed["total_crc"]
    if not parts or summary is None:
        raise ProvisioningError("BAD_FRAME")
    if sorted(parts) != list(range(1, len(parts) + 1)):
        raise ProvisioningError("BAD_FRAME: thiếu chunk")
    tlv = b"".join(parts[index] for index in sorted(parts))
    if _crc(tlv) != summary:
        raise ProvisioningError("CRC_MISMATCH: tổng khung không khớp")
    fields = legacy.parse_frame(FRAME_PREFIX + base64.b64encode(tlv)
                                + b"," + f"{summary:08x}".encode() + b"\n")
    if TAG_DEVICE_KEY not in fields or len(fields[TAG_DEVICE_KEY]) != DEVICE_KEY_LEN:
        raise ProvisioningError("BAD_TLV: tag=9 phải là device key 32 byte")
    return fields


def total_crc(chunks: list[bytes]) -> int:
    parts = []
    for line in chunks:
        parsed = parse_chunk(line)
        if parsed["kind"] == "chunk":
            parts.append(parsed["data"])
    if not parts:
        raise ProvisioningError("BAD_FRAME")
    return _crc(b"".join(parts))


def fingerprint(tlv: bytes) -> str:
    """Fingerprint công khai của khung; không đảo ngược được secret."""
    return hashlib.sha256(tlv).hexdigest()[:16]


def _write_chunks(lines: list[bytes], out_path: str) -> None:
    path = Path(out_path)
    if path.is_dir():
        raise ProvisioningError(f"--out phải là file, không phải thư mục: {path}")
    path.write_bytes(b"".join(lines))
    try:
        os.chmod(path, 0o600)
    except (AttributeError, OSError):
        pass
    print(f"Đã ghi {len(lines)} dòng khung (nhạy cảm) vào {path} — không commit file này.")


def _send_chunks(lines: list[bytes], port: str) -> None:
    try:
        import serial  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ProvisioningError("cần pyserial để dùng --port: pip install pyserial") from exc
    try:
        with serial.Serial(port, legacy.UART_BAUD, timeout=5) as link:
            ready = link.readline().strip()
            if ready != b"+READY":
                raise ProvisioningError("bo chưa gửi +READY (sai cổng/baud hoặc đã có config)")
            for line in lines:
                link.write(line)
                reply = link.readline().strip().decode("ascii", errors="replace")
                if not reply.startswith("+"):
                    raise ProvisioningError(f"bo từ chối chunk: {reply or 'không có phản hồi'}")
    except ProvisioningError:
        raise
    except Exception as exc:
        raise ProvisioningError(f"lỗi UART {port}: {exc}") from exc
    print("Bo trả +ACK: device key 32 byte đã lưu vào NVS.")


def _common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--site", default="SITE_01")
    parser.add_argument("--device-type", default="light",
                        choices=["light", "led_display", "gateway"])
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--client-id", help="mặc định = device-id")
    parser.add_argument("--broker-host", required=True)
    parser.add_argument("--broker-port", type=int, required=True)
    parser.add_argument("--wifi-ssid", default=os.environ.get("PCCOM_WIFI_SSID"))
    parser.add_argument("--wifi-pass-file")
    parser.add_argument("--ca-pem", required=True)
    parser.add_argument("--cert-pem", required=True)
    parser.add_argument("--key-pem", required=True)
    parser.add_argument("--signing-secret-file",
                        help="file chứa HMAC master secret; chỉ đọc trên host")
    parser.add_argument("--chunk-bytes", type=int, default=DEFAULT_CHUNK_BYTES)
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--out", help="ghi các dòng khung vào file")
    destination.add_argument("--port", help="gửi khung qua UART, ví dụ COMx")


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Provisioning ESP32: dẫn xuất device key trên host, CRC từng chunk."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="tạo khung chunked")
    _common_arguments(build)
    send = sub.add_parser("send", help="tạo và gửi khung qua UART")
    _common_arguments(send)
    show = sub.add_parser("show", help="chỉ in độ dài + fingerprint")
    show.add_argument("--in", dest="input_file", required=True)
    # Cú pháp flat (không có subcommand) được hiểu là `build` để tương thích
    # với các script/audit cũ gọi trực tiếp parse_args([...]).
    if argv is not None and argv and argv[0] not in ("build", "send", "show"):
        argv = ["build", *argv]
    args = parser.parse_args(argv)
    if args.command in ("build", "send"):
        if not args.client_id:
            args.client_id = args.device_id
        if not args.wifi_ssid:
            parser.error("--wifi-ssid hoặc PCCOM_WIFI_SSID là bắt buộc")
    return args


def main(argv: Optional[list[str]] = None) -> int:
    _configure_utf8_streams()
    try:
        args = parse_args(argv)
        if args.command == "show":
            raw = Path(args.input_file).read_bytes()
            fields = parse_chunked(raw)
            lines = [line for line in raw.splitlines() if line.strip()]
            print(
                f"PROV SHOW version={legacy.PROVISION_VERSION} "
                f"lines={len(lines)} tlv_bytes={sum(len(v) for v in fields.values()) + 3 * len(fields)} "
                f"tags={len(fields)} device_key_len={len(fields[TAG_DEVICE_KEY])} "
                f"fingerprint={fingerprint(tlv_from_chunked(raw))}"
            )
            return 0
        frame, tlv, crc = build_frame(args)
        lines = chunk_frame(frame, args.chunk_bytes)
        fields = parse_frame(frame)  # tự kiểm chứng trước khi ghi/gửi
        print(
            f"provision site={args.site} device={args.device_id} "
            f"tlv_bytes={len(tlv)} chunks={len(lines) - 1} crc32={crc:08x} "
            f"device_key_len={len(fields[TAG_DEVICE_KEY])} "
            f"fingerprint={fingerprint(tlv)}"
        )
        if args.command == "build" or args.out:
            _write_chunks(lines, args.out)
        else:
            _send_chunks(lines, args.port)
        return 0
    except (ProvisioningError, OSError) as exc:
        print(f"Lỗi provisioning: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Đã hủy.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
