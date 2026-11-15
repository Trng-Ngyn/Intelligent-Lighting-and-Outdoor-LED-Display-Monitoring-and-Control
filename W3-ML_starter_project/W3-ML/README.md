# W3-ML – AI Baseline phát hiện bất thường thiết bị LED

> **Lưu ý dữ liệu:** `data/raw/pilot_50_led_synthetic.csv` là dữ liệu **mô phỏng**, không phải dữ liệu đo thực tế từ 50 đèn Pilot. Không dùng kết quả mô phỏng để tuyên bố hiệu năng thực tế khi nghiệm thu.

## 1. Mục tiêu
- Chuẩn hóa mã lỗi F01–F04.
- Định nghĩa quy trình gán nhãn Ground Truth.
- Tạo dữ liệu mô phỏng 50 thiết bị để kiểm thử pipeline.
- Xây dựng baseline phát hiện dị thường bằng Isolation Forest và Autoencoder.
- Đánh giá Precision, Recall, F1-score và False Positive Rate.

## 2. Cấu trúc
```text
W3-ML/
├── documents/       # Đặc tả và quy trình
├── data/
│   ├── raw/         # Dữ liệu mô phỏng ban đầu
│   ├── processed/   # Dữ liệu sau tiền xử lý
│   └── labeled/     # Dữ liệu đã gán nhãn
├── src/             # Mã nguồn Python
└── reports/         # Kết quả chạy mô hình
```

## 3. Yêu cầu
- Python 3.12
- Các thư viện trong `requirements.txt`

Cài đặt:
```bash
python -m pip install -r requirements.txt
```

## 4. Chạy lần lượt
Mở Terminal tại thư mục `W3-ML`:

```bash
python src/generate_synthetic_data.py
python src/preprocess.py
python src/isolation_forest.py
python src/autoencoder.py
python src/evaluate.py
```

Các kết quả sẽ được lưu trong `data/processed/` và `reports/`.

## 5. Ý nghĩa nhãn
- `fault_code`: `NORMAL`, `F01`, `F02`, `F03`, `F04`.
- `anomaly_label`: `0` = bình thường, `1` = có bất thường.
- `fault_codes`: có thể chứa nhiều mã lỗi, phân cách bằng dấu `;`.
- `is_synthetic`: luôn bằng `1` trong bộ dữ liệu demo.

## 6. Nguyên tắc nghiệm thu
1. Thay dữ liệu mô phỏng bằng dữ liệu telemetry thật khi được cung cấp.
2. Chốt ngưỡng F02/F03/F04 với nhóm kỹ thuật và chủ sở hữu thiết bị.
3. Đánh giá trên tập kiểm thử tách biệt theo thời gian hoặc theo thiết bị.
4. Báo cáo rõ đây là kết quả mô phỏng hay thực nghiệm thực tế.
