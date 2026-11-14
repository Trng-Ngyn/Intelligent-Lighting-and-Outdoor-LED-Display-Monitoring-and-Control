# W3-ML – Ground Truth Labeling Protocol

**Phiên bản:** 0.1 – Bản dự thảo

## 1. Mục tiêu
Tạo nhãn tham chiếu nhất quán cho telemetry của 50 đèn Pilot để huấn luyện/đánh giá và kiểm tra chất lượng dữ liệu.

## 2. Đơn vị gán nhãn
Một dòng dữ liệu tương ứng một lần đo của một thiết bị tại một timestamp. Mỗi dòng phải có `device_id` và `timestamp`.

## 3. Trường dữ liệu tối thiểu
`device_id`, `timestamp`, `driver_temp_c`, `led_temp_c`, `voltage_v`, `current_a`, `power_w`, `lumen_pct`, `display_sync_ok`, `sync_error_count`.

Nên bổ sung model thiết bị, vị trí lắp đặt, firmware, trạng thái bật/tắt, nhiệt độ môi trường, mã cảm biến và trạng thái hiệu chuẩn.

## 4. Quy trình gán nhãn
1. **Tiếp nhận:** lưu bản raw bất biến, ghi nguồn, thời điểm nhận, đơn vị đo và người bàn giao.
2. **Kiểm tra chất lượng:** kiểm tra thiếu dữ liệu, timestamp trùng/không hợp lệ, giá trị ngoài dải vật lý và cảm biến lỗi.
3. **Chuẩn hóa:** quy đổi đơn vị, đồng bộ múi giờ, sắp xếp theo `device_id`, `timestamp`.
4. **Áp dụng quy tắc:** dùng taxonomy đã được phê duyệt; không tự ý đổi ngưỡng.
5. **Xác minh:** người gán nhãn thứ hai kiểm tra các trường hợp lỗi và trường hợp sát ngưỡng.
6. **Phân xử:** bất đồng được chuyển cho người phụ trách kỹ thuật; lưu lý do và quyết định.
7. **Đóng phiên bản:** lưu phiên bản taxonomy, người gán nhãn, ngày gán nhãn và phiên bản dataset.

## 5. Nhãn
- `NORMAL`: không thỏa điều kiện lỗi.
- `F01`–`F04`: mã lỗi cụ thể.
- `MULTI_FAULT`: nhiều lỗi cùng lúc (dùng trong báo cáo nếu cần).
- `UNKNOWN`: chưa đủ bằng chứng.
- `DATA_QUALITY_ISSUE`: dữ liệu không đáng tin để kết luận.

Không ép `UNKNOWN` hoặc `DATA_QUALITY_ISSUE` thành NORMAL.

## 6. Chia tập dữ liệu
Không chia ngẫu nhiên từng dòng nếu các dòng cùng thiết bị/thời gian có tương quan. Ưu tiên:
- chia theo thời gian (train trước, test sau), hoặc
- chia theo thiết bị (thiết bị train khác thiết bị test).
Không để bản ghi gần như trùng nhau lọt vào cả train và test.

## 7. Kiểm soát chất lượng
- Kiểm tra 100% trường hợp F01 sát 80°C và các trường hợp lỗi hiếm.
- Lấy mẫu kiểm tra chéo các dòng NORMAL.
- Báo cáo tỷ lệ đồng thuận giữa người gán nhãn.
- Lưu log mọi thay đổi nhãn.

## 8. Phân biệt nhãn quy tắc và xác nhận thực tế
Nhãn tạo tự động từ ngưỡng telemetry là **rule-derived label**. Ground Truth đáng tin cậy cần được xác minh bằng kiểm tra kỹ thuật, nhật ký bảo trì, thiết bị đo chuẩn hoặc xác nhận của chuyên gia. Dữ liệu demo trong dự án này chỉ là nhãn mô phỏng.
