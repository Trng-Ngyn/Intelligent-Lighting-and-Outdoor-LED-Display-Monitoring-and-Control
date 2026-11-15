# Hợp đồng dữ liệu v1

Các mẫu dùng JSON Schema Draft 2020-12. Định danh, số thứ tự và phiên bản được
kiểm ở adapter, Ingestion và Application Core theo vai trò. Cấu hình validator
bật kiểm `format` cho timestamp. UTC dùng hậu tố Z. Lịch giữ time zone IANA.

- `telemetry`: dữ liệu gateway. Cloud đặt `received_time` ở bản ghi chuẩn hóa
  sau xác thực. Khóa nhận lại là `tenant_id + gateway_id + message_id`.
- `receipt`: đánh dấu dữ liệu đã ghi bền hoặc đã cách ly do lỗi. Gateway xóa
  bản ghi spool sau receipt phù hợp. Với lỗi không đọc được ID, giữ ở hàng lỗi
  riêng để điều tra, thay vì tiếp tục gửi lại vô hạn.
- `command` và `manifest`: đây là payload trước khi ký. Đường truyền thực tế
  dùng Compact JWS ES256 trên byte đã được ký. Mẫu JSON chưa ký chỉ dùng để
  kiểm schema. Gateway gắn `control_epoch` và `target_rev` với journal bền vững.
- `ack`: kết quả ứng dụng. Chỉ dùng `verified` khi có feedback thiết bị hoặc
  đo độc lập được chấp thuận. Broker PUBACK có ý nghĩa riêng.

Core và gateway xác minh các ràng buộc nghiệp vụ ngoài schema: identity so với
topic/registry, hạn thời gian và quan hệ giữa các timestamp, version và thứ tự
lệnh, khả năng và giới hạn từng tài sản, mapping metric ↔ unit, múi giờ hợp lệ,
thẩm quyền và sự tách biệt của người duyệt, chữ ký và object hash. Với `object_key`
dùng khóa đã đăng ký ở Core; player lưu cache bằng tên tạo nội bộ theo hash.
