# SCRUM-29 / W5-DE — Hướng dẫn bàn giao

Ngày: 27/11/2026. Người phụ trách: Lê Tiến Công.

## 1. Bộ mã này làm gì?

- Giữ nguyên DDL Gate G1 và JSON Schema Draft-07 trong docs/data_contracts.
- Nhận MQTT telemetry/v1/#; cấu hình Staging còn nhận topic Arduino cũ và envelope northbound của gateway.
- Ánh xạ mã MQTT sang UUID đã đăng ký. Staging từ chối thiết bị chưa đăng ký hoặc payload giả danh thiết bị khác.
- COPY theo lô 500 bản ghi, flush 0,2 giây, transaction và receipt ledger chống trùng.
- Chỉ ACK MQTT QoS 1 sau khi ghi transaction thành công. Bản tin lỗi được lưu bền trong lighting.ingestion_dlq, rồi xuất ra dlq/v1/telemetry.
- Phân biệt khoảng điện năng Wh với chỉ số công tơ Wh. Chênh lệch công tơ được đánh dấu estimated; mẫu đầu/reset/đồng hồ chưa đồng bộ không bị biến thành điện năng 0.
- Công tơ đến muộn được tính lại từ mẫu ngay trước thời điểm bị ảnh hưởng. Dữ liệu interval không phải quét lại toàn bộ lịch sử.

## 2. Nộp thủ công lên GitHub

Giải nén W5_DE_SOURCE.zip. ZIP chứa các đường dẫn tính từ gốc repository, không phải một repository mới.

1. Mở nhánh feature/w5-de-ingestion của bạn.
2. Chọn Add file → Upload files tại gốc repository.
3. Kéo **nội dung** thư mục vừa giải nén: src, sql, tools, tests, docs và các tệp gốc. Giữ đúng cấu trúc; không kéo thư mục bao ngoài có tên W5_DE_SOURCE.
4. Không tải .env.w5, .staging, khóa, chứng chỉ, node_modules hoặc .venv.
5. Commit: SCRUM-29: integrate registry-bound MQTT ingestion.

Hướng dẫn và báo cáo đã nằm trong docs/w5/de; không cần tạo thêm bản trùng ở gốc repo. docs/w5/de/manifest.json liệt kê chính xác các tệp trong gói.

Ba gói DE, FE, TL bổ sung cho nhau. Để chạy toàn hệ thống, giải nén **cả ba** vào cùng một bản clone main. Với các nhánh nộp riêng, Tech Lead cần tích hợp đủ ba gói trước khi đánh giá workflow W5 tổng thể. Không coi việc upload thành công là đã nghiệm thu Staging.

## 3. Tiếp tục môi trường Windows local đã có

Mở PowerShell tại C:\Users\ACER\W5-DE, sau khi chép đè mã nguồn đúng đường dẫn:

~~~powershell
docker compose --env-file .env.w5 -f docker-compose.w5.yml -f docker-compose.w5.services.yml up -d --build --wait
docker exec pccom-w5-ingestion python publish_demo.py --mode demo
docker exec pccom-w5-ingestion python publish_demo.py --mode benchmark --count 10000
~~~

Giữ nguyên volume và mật khẩu đã dùng. Không chạy lại DDL để xóa/khởi tạo lại dữ liệu đang có. Môi trường local này chỉ bind broker 1883 và database 5433 vào 127.0.0.1; bản Staging mTLS nằm trong gói TL.

Mong đợi: 2 bản tin hợp lệ được lưu, 1 bản tin lỗi vào DLQ, replay vẫn 2 dòng; benchmark phải có sent_unique = stored_unique = 10000 và target_over_500 = true. Đây là dữ liệu tổng hợp, không phải ESP32 thật.

## 4. Khai báo thiết bị thật

Tech Lead và IoT điền deploy/staging/registry.example.json trước khi bootstrap:

| Trường | Nguồn thông tin |
| --- | --- |
| tenant_id, site_id, asset_id, device_id, location_id | UUID trong mô hình Gate G1; không tự đoán từ tên MQTT |
| field_site, device_code | Mã site/thiết bị thật do IoT xác nhận |
| kind | lighting hoặc led |
| energy_mode | interval, counter hoặc none đúng với thiết bị |
| latitude, longitude | Tọa độ thật; có thể để cả hai null khi chưa đo |
| heartbeat_s | Chu kỳ telemetry thực tế |
| command_mode | southbound, northbound hoặc legacy |
| trust_legacy_clock | Chỉ bật sau khi đã xác minh đồng bộ NTP của firmware cũ |
| is_demo | false cho thiết bị thật |

Mẫu registry cố ý chứa REPLACE_WITH... và không thể triển khai nếu chưa điền. Chế độ --demo của TL tạo bộ thiết bị tổng hợp riêng, có nhãn DEMO trên web.

Topic cũ pccom/lighting/SITE_01/LGT_NODE_001/telemetry được chuẩn hóa qua binding. Topic native telemetry/v1/{field_site}/{light|led_display}/{device_code} vẫn là đầu vào yêu cầu của Jira.

Không sửa các Schema Draft-07 đã duyệt để hợp thức hóa payload sai. Ví dụ đơn vị đúng: W, Wh, V, A, %, °C và 1; metrics luôn giữ chất lượng đo.

## 5. Kiểm thử tự động trên Linux

~~~bash
python3 -m venv .venv-de
.venv-de/bin/pip install -r requirements-de-test.txt
PYTHONPATH=src .venv-de/bin/python -m pytest tests/w5/test_ingestion.py -q -s
~~~

Bài kiểm thử này khởi tạo PostgreSQL 16 dùng một lần và giữ các định nghĩa bảng/ràng buộc G1. Nó không thay thế kiểm thử extension TimescaleDB, MQTT hoặc VPS.

Khi đã ghép cả ba gói, xem hướng dẫn TL để chạy tools/staging/verify.py trong Docker. Script đó kiểm tra MQTT mTLS, ghi 10.000 bản tin, tốc độ >500/s, DLQ, chống trùng và hai policy aggregate giờ chạy tự động; nó không gọi refresh thủ công để giả lập tự động.

Đã chạy thêm bài toàn tuyến native bằng broker mTLS và extension TimescaleDB thật: 10.000/10.000 bản tin, 1.259,12/s; 8 bucket aggregate khớp raw và sáu job Success. tools/staging/native_acceptance.py trong gói TL chạy lại được bài này và nối cả web/dimming. Đây là thiết bị mô phỏng, tách khỏi nghiệm thu ESP32; xem TEST_REPORT.md để biết chính xác phiên bản và bằng chứng.

## 6. Đối soát ESP32 thật

IoT lưu log nguồn JSONL, mỗi dòng gồm tenant_id, site_id, asset_id và message_id đã phát. Giữ nguyên ID khi retry. Công cụ hỗ trợ cả message_id UUID và ID chuỗi cũ bằng phép UUID5 gắn với asset đã đăng ký.

~~~bash
PYTHONPATH=src python tools/data/reconcile.py esp32-published.jsonl
~~~

Thiết lập PGHOST/PGPORT/PGDATABASE/PGUSER và PGPASSWORD_FILE cho database cần kiểm tra. Kết quả phải có source_unique > 0, missing rỗng, coverage_pct = 100 và passed = true.

Đây là đối soát ID duy nhất trong khoảng thử, không phải cam kết không mất dữ liệu trong mọi sự cố. Firmware Arduino hiện dùng PubSubClient publish QoS 0 và số đo mô phỏng; cần IoT hoàn thành MQTT/TLS, log/outbox hoặc QoS phù hợp và cảm biến thật trước khi nghiệm thu.

## 7. Điện năng theo giờ

DDL G1 cộng energy_interval_wh với clock_quality = synced và quality measured/estimated. Không cộng trực tiếp các chỉ số công tơ tích lũy.

Hai policy giờ chạy mỗi 15 phút, tính lại cửa sổ 14 ngày. Sau khi nạp dữ liệu vào giờ đã đóng, chờ policy chạy rồi so tổng dữ liệu gốc và view theo cùng tenant/site/asset/bucket. Dữ liệu quá cửa sổ này cần kế hoạch backfill riêng.

Quy ước G1 gán khoảng điện năng vào bucket theo thời điểm kết thúc, với offset 1 microsecond. Muốn phân bổ chính xác quanh ranh giới giờ, IoT phải phát interval có mốc đo phù hợp. Không có đủ mẫu/đồng hồ thì không thể tự suy ra điện năng thực tế chính xác ở từng giờ.

## 8. Điều kiện chốt Done

Chỉ chốt SCRUM-29 khi đã có: Staging thật chạy, ESP32 thật gửi telemetry được đối soát 100% trong bài thử, tốc độ MQTT → TimescaleDB >500/s, và aggregate tự cập nhật khớp dữ liệu nguồn. Báo cáo đi kèm tách rõ phần đã kiểm thử và phần còn cần môi trường thật.
