# W3-ML – Fault Taxonomy F01–F04

**Phiên bản:** 0.1 – Bản dự thảo  
**Phạm vi:** Thiết bị chiếu sáng LED và màn hình LED trong Pilot.

## 1. Mục đích
Thống nhất tên mã lỗi, dữ liệu cần quan sát, điều kiện gắn nhãn và cách xác nhận. Taxonomy này là nền tảng cho gán nhãn Ground Truth và đánh giá mô hình AI.

## 2. Bảng phân loại

| Mã | Tên lỗi | Định nghĩa | Dữ liệu tối thiểu |
|---|---|---|---|
| F01 | Quá nhiệt Driver/LED | Nhiệt độ Driver hoặc LED vượt 80°C | timestamp, device_id, driver_temp_c, led_temp_c |
| F02 | Bất thường điện năng / rò rỉ tiêu thụ | Công suất tiêu thụ lệch bất thường hoặc dòng điện tăng đột biến | voltage_v, current_a, power_w |
| F03 | Suy hao quang thông | Quang thông/độ sáng giảm theo thời gian so với mức tham chiếu ban đầu | lumen_pct, baseline_lumen_pct |
| F04 | Mất đồng bộ hiển thị màn hình LED | Trạng thái đồng bộ hoặc tín hiệu hiển thị bị gián đoạn | display_sync_ok, sync_error_count |

## 3. Quy tắc nhận diện

### F01 – Quá nhiệt
- Kích hoạt khi `driver_temp_c > 80` hoặc `led_temp_c > 80`.
- Đúng bằng 80°C không thỏa điều kiện `> 80°C`.
- Nếu cảm biến nhiệt bị thiếu hoặc ngoài dải hợp lệ, gắn `DATA_QUALITY_ISSUE`, không tự động gắn F01.

### F02 – Bất thường điện năng
Đề bài chưa cung cấp ngưỡng số cụ thể. Bản mô phỏng dùng quy tắc tạm:
- Dòng điện tăng đột biến: `current_a > 1.25 × current_baseline_a`; hoặc
- Công suất lệch: `abs(power_w - power_baseline_w) / power_baseline_w > 0.20`.
- Các hệ số 1.25 và 20% là **giả định mô phỏng**, phải được kỹ thuật xác nhận trước nghiệm thu.

### F03 – Suy hao quang thông
Đề bài chưa cung cấp ngưỡng suy hao. Bản mô phỏng dùng:
- `lumen_pct < 80` (giảm hơn 20% so với mức tham chiếu 100%).
- Đây là ngưỡng dự thảo; cần xác nhận loại đèn, phương pháp đo, điều kiện môi trường và thời gian tích lũy.

### F04 – Mất đồng bộ hiển thị
Bản mô phỏng dùng:
- `display_sync_ok == 0` hoặc `sync_error_count > 0`.
- Cần xác nhận nguồn tín hiệu và cách thiết bị ghi nhận trạng thái đồng bộ.

## 4. Mức độ ưu tiên đề xuất
- Critical: F01 khi vượt 80°C; F04 nếu màn hình mất hiển thị hoàn toàn.
- High: F02 có dòng điện tăng đột biến; F03 suy hao vượt ngưỡng vận hành.
- Các mức này là đề xuất phân loại vận hành, không thay thế quy định an toàn của nhà sản xuất.

## 5. Quy tắc đa lỗi
Một bản ghi có thể đồng thời vi phạm nhiều điều kiện. Trong CSV:
- `fault_codes` lưu tất cả mã lỗi, phân cách bằng `;`.
- `fault_code` lưu mã đầu tiên theo thứ tự ưu tiên F01, F02, F03, F04; nếu không có lỗi là `NORMAL`.
- `anomaly_label=1` nếu có ít nhất một mã lỗi.

## 6. Các điểm cần chủ sở hữu dữ liệu xác nhận
1. F02: định mức dòng/công suất theo từng model đèn và mức lệch cho phép.
2. F03: dữ liệu lumen đo bằng cảm biến nào, baseline lúc nào, ngưỡng suy hao và thời gian xác nhận.
3. F04: định nghĩa mất đồng bộ, số lần lỗi liên tiếp và khoảng thời gian debounce.
4. F01: vị trí cảm biến, sai số, chu kỳ lấy mẫu và quy tắc duy trì vượt ngưỡng.
