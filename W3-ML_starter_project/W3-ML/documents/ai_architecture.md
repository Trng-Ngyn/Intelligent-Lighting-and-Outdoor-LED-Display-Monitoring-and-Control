# W3-ML – AI Baseline Architecture

## 1. Pipeline
Telemetry CSV → kiểm tra chất lượng → tiền xử lý → tạo feature → mô hình dị thường → ngưỡng điểm bất thường → kết quả cảnh báo → đánh giá.

## 2. Feature đầu vào
- driver_temp_c, led_temp_c
- voltage_v, current_a, power_w
- lumen_pct
- display_sync_ok, sync_error_count

`device_id`, `timestamp`, nhãn và mã lỗi không đưa trực tiếp vào mô hình.

## 3. Isolation Forest
- Chuẩn hóa/điền dữ liệu thiếu.
- Huấn luyện Isolation Forest trên feature telemetry.
- `contamination` là tham số ước lượng tỷ lệ bất thường, cần tinh chỉnh trên validation.
- `predict=-1` được chuyển thành anomaly prediction 1.

## 4. Autoencoder
- Mạng Dense đối xứng nén rồi tái tạo feature.
- Huấn luyện ưu tiên trên dữ liệu NORMAL đã được xác minh.
- Dùng reconstruction error làm anomaly score.
- Ngưỡng được chọn trên validation, không chọn trên test.

## 5. Đánh giá
So sánh dự đoán nhị phân với nhãn tham chiếu:
- Precision = TP / (TP + FP)
- Recall = TP / (TP + FN)
- F1 = 2 × Precision × Recall / (Precision + Recall)
- FPR = FP / (FP + TN)

Với dữ liệu nhiều lỗi, baseline hiện tại đánh giá phát hiện `NORMAL` so với `ANOMALY`. Phân loại đúng từng F01–F04 là bước mở rộng riêng.

## 6. Giới hạn
Dữ liệu hiện tại là mô phỏng. Kết quả chỉ xác nhận code chạy và pipeline hoạt động, không chứng minh mô hình đạt hiệu năng trên 50 đèn thật.
