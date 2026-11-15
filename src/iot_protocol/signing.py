"""Ký và xác thực bản tin MQTT 5 bằng HMAC-SHA256.

Vị trí trong luồng: Simulator (hoặc Cloud) ký trước khi publish; phía nhận
xác thực topic + correlation_id + ts_ms + payload trước khi xử lý.

Tại sao dùng HMAC thay vì chữ ký bất đối xứng: thiết bị edge giá rẻ, cần tính
toán nhẹ và cấu hình đơn giản; khóa được chia sẻ theo từng thiết bị (dẫn xuất
từ master secret), nên một thiết bị bị lộ khóa không làm giả được thiết bị
khác.

Xem docs/specifications/MQTT5_COMMUNICATION_PROTOCOL.md, mục "User Properties
và chữ ký".
"""

from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from collections import deque
from typing import Callable, Deque, Optional

CANONICAL_VERSION = "v1"
SIGNATURE_ALGORITHM = "HMAC-SHA256"
DEFAULT_REPLAY_WINDOW_MS = 30_000
DEFAULT_FUTURE_SKEW_MS = 30_000


class SignatureError(ValueError):
    """Chữ ký không hợp lệ hoặc thiếu dữ liệu để xác thực."""


class ReplayError(ValueError):
    """Bản tin nằm ngoài cửa sổ thời gian hoặc correlation_id đã được xử lý."""


def now_ms() -> int:
    """Trả về timestamp epoch theo mili-giây (dùng cho header ts_ms)."""
    return int(time.time() * 1000)


def new_correlation_id() -> str:
    """Sinh correlation_id UUID4 mới cho một message/lệnh."""
    return str(uuid.uuid4())


def derive_device_key(
    master_secret: str,
    site_id: str,
    device_type: str,
    device_id: str,
) -> bytes:
    """Dẫn xuất khóa HMAC riêng cho từng thiết bị từ master secret.

    Tham số:
        master_secret: Khóa gốc đọc từ config/biến môi trường, không commit.
        site_id, device_type, device_id: Định danh thiết bị.

    Trả về:
        Khóa 32 byte dùng trực tiếp cho HMAC-SHA256.

    Ngoại lệ:
        SignatureError: Nếu master_secret rỗng.
    """
    if not master_secret:
        raise SignatureError("master_secret rỗng, không thể dẫn xuất khóa thiết bị")

    # Dùng đúng chuỗi định danh giống topic để Cloud và Simulator tính ra cùng
    # một khóa mà không cần lưu 50-52 khóa riêng trong file cấu hình.
    identity = f"{site_id}/{device_type}/{device_id}".encode("utf-8")
    return hmac.new(
        master_secret.encode("utf-8"),
        identity,
        hashlib.sha256,
    ).digest()


def canonical_string(
    topic: str,
    correlation_id: str,
    ts_ms: int,
    payload: bytes | str,
) -> bytes:
    """Tạo chuỗi canonical để ký.

    Chuỗi canonical có dạng (phân tách bằng newline):
        v1
        {topic}
        {correlation_id}
        {ts_ms}
        {payload}

    Tại sao có version và newline: version cho phép đổi thuật toán sau này mà
    không phá chữ ký cũ; newline tách các trường để tránh nhập nhằng kiểu
    "ab" + "c" và "a" + "bc". Payload là trường cuối nên có thể chứa newline.

    Tham số:
        topic: Topic thực tế đã publish.
        correlation_id: UUID của message.
        ts_ms: Timestamp epoch mili-giây.
        payload: Payload dạng bytes hoặc str (UTF-8).

    Trả về:
        Chuỗi bytes canonical.
    """
    if isinstance(payload, str):
        payload_bytes = payload.encode("utf-8")
    elif isinstance(payload, (bytes, bytearray)):
        payload_bytes = bytes(payload)
    else:
        raise SignatureError("payload phải là str hoặc bytes")

    header = "\n".join(
        [CANONICAL_VERSION, topic, correlation_id, str(int(ts_ms))]
    ).encode("utf-8")
    return header + b"\n" + payload_bytes


def sign_message(
    secret: bytes,
    topic: str,
    correlation_id: str,
    ts_ms: int,
    payload: bytes | str,
) -> str:
    """Ký message và trả về chữ ký hex lowercase.

    Tham số:
        secret: Khóa HMAC đã dẫn xuất cho thiết bị.
        topic, correlation_id, ts_ms, payload: Các trường của chuỗi canonical.

    Trả về:
        Chuỗi hex 64 ký tự.

    Ngoại lệ:
        SignatureError: Nếu secret rỗng.
    """
    if not secret:
        raise SignatureError("secret rỗng, không thể ký")
    message = canonical_string(topic, correlation_id, ts_ms, payload)
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def verify_message(
    secret: bytes,
    topic: str,
    correlation_id: str,
    ts_ms: int,
    payload: bytes | str,
    signature: str,
) -> bool:
    """Xác thực chữ ký theo kiểu so sánh hằng thời gian.

    Tham số:
        secret: Khóa HMAC của thiết bị.
        topic, correlation_id, ts_ms, payload: Dữ liệu gốc.
        signature: Chữ ký hex nhận từ User Property.

    Trả về:
        True nếu hợp lệ, False nếu sai/thiếu.

    Ngoại lệ:
        SignatureError: Nếu secret rỗng hoặc định dạng chữ ký sai.
    """
    if not isinstance(signature, str) or len(signature) != 64:
        return False
    try:
        int(signature, 16)
    except ValueError:
        return False

    expected = sign_message(secret, topic, correlation_id, ts_ms, payload)
    return hmac.compare_digest(expected, signature.lower())


class ReplayGuard:
    """Bộ nhớ tạm chống replay theo ts_ms và correlation_id.

    Cơ chế:
    - ts_ms phải nằm trong [now - window_ms, now + future_skew_ms].
    - correlation_id chưa từng xuất hiện trong cửa sổ.
    - Các mục cũ hơn cửa sổ được dọn tự động để bộ nhớ không tăng vô hạn.

    Đối tượng này không thread-safe; mỗi thiết bị nên dùng một instance trong
    một luồng xử lý message.
    """

    def __init__(
        self,
        window_ms: int = DEFAULT_REPLAY_WINDOW_MS,
        future_skew_ms: int = DEFAULT_FUTURE_SKEW_MS,
        clock_ms: Optional[Callable[[], int]] = None,
    ) -> None:
        if window_ms <= 0:
            raise ValueError("window_ms phải > 0")
        if future_skew_ms < 0:
            raise ValueError("future_skew_ms phải >= 0")
        self.window_ms = window_ms
        self.future_skew_ms = future_skew_ms
        self._clock_ms = clock_ms or now_ms
        self._seen: Deque[tuple[int, str]] = deque()
        self._seen_ids: set[str] = set()

    def _prune(self, now: int) -> None:
        """Loại các correlation_id đã ra khỏi cửa sổ replay."""
        threshold = now - self.window_ms
        while self._seen and self._seen[0][0] < threshold:
            _, old_id = self._seen.popleft()
            self._seen_ids.discard(old_id)

    def check_and_record(self, correlation_id: str, ts_ms: int) -> None:
        """Kiểm tra rồi ghi nhận một correlation_id.

        Ngoại lệ:
            ReplayError: Nếu timestamp lệch quá cửa sổ hoặc ID đã được dùng.
        """
        if not correlation_id:
            raise ReplayError("Thiếu correlation_id")

        now = self._clock_ms()
        if ts_ms < now - self.window_ms:
            raise ReplayError(
                f"ts_ms quá cũ: {ts_ms} (now={now}, window={self.window_ms}ms)"
            )
        if ts_ms > now + self.future_skew_ms:
            raise ReplayError(
                f"ts_ms ở tương lai: {ts_ms} (now={now}, skew={self.future_skew_ms}ms)"
            )

        self._prune(now)
        if correlation_id in self._seen_ids:
            raise ReplayError(f"correlation_id đã được xử lý: {correlation_id}")

        self._seen.append((ts_ms, correlation_id))
        self._seen_ids.add(correlation_id)

    def __len__(self) -> int:
        """Số correlation_id đang được ghi nhớ (phục vụ kiểm thử/log)."""
        return len(self._seen_ids)
