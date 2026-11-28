# SCRUM-29 / W5-DE — Báo cáo kiểm thử

Ngày: 27/11/2026. Đã hoàn thành mã và kiểm thử tích hợp phần mềm. Nghiệm thu VPS/ESP32 vật lý chưa được thực hiện.

## 1. Kiểm thử toàn tuyến mới

Đã chạy các tiến trình thật: Mosquitto 2.0.22 với mTLS/ACL/retain plugin → worker → PostgreSQL 17.11 + extension TimescaleDB 2.32.0 → FastAPI → trình duyệt Chromium. Database mới được khởi tạo bằng nguyên DDL Gate G1. Registry gồm ba thiết bị tổng hợp, có nhãn DEMO; không dùng ESP32 thật.

Phiên bản PostgreSQL 17.11 được đối chiếu với metadata image timescale/timescaledb:2.32.0-pg17 ở thời điểm kiểm tra. Đây là chạy native trên Linux, không phải kết quả Docker image/VPS đã chạy.

| Kiểm tra | Kết quả thực tế |
| --- | --- |
| Hypertables telemetry_lighting và telemetry_led | PASS, extension TimescaleDB thật |
| MQTT telemetry/v1/# qua mTLS | PASS |
| Demo hợp lệ/lỗi/replay | 2 hợp lệ, 1 DLQ, replay giữ 2 dòng |
| Benchmark MQTT → TimescaleDB | 10.000/10.000 bản tin, 7,942 giây, **1.259,12 bản ghi/giây** |
| Aggregate giờ tự cập nhật | PASS, 8 bucket đối chiếu, 0 sai lệch |
| Hai policy giờ | Được tạm tăng tần suất thành 5 giây để kiểm thử, sau đó trả về 15 phút |
| Sáu policy giờ/ngày/tháng | scheduled=true, last_run_status=Success |
| Từ chối MQTT client không có certificate | PASS |
| Health identity bị cấm publish telemetry | PASS |
| API/Web → MQTT → telemetry → DB | PASS, 6 lệnh riêng/nhóm được telemetry xác nhận |

Không gọi refresh aggregate thủ công trong bài kiểm tra tự cập nhật. Tổng receipt sau bài thử là 10.050 do còn có heartbeat thiết bị mô phỏng; benchmark đếm riêng đúng 10.000 message_id của nó. Chênh lệch điện năng được so ở ngưỡng 0,000001 Wh.

Bằng chứng: evidence/native-acceptance.txt và evidence/native-result.json. Cách chạy lại nằm trong hướng dẫn TL, bằng tools/staging/native_acceptance.py hoặc verify.py trên Compose.

## 2. Kiểm thử ràng buộc và lỗi

Bộ pytest có **16 PASS**: 8 DE, 5 API, 2 PKI/cấu hình và 1 trình duyệt. Trong bộ này PostgreSQL 16 dùng một lần giữ bảng/ràng buộc G1; các view phục vụ test serialization không được coi là TimescaleDB. Bằng chứng Timescale riêng là bài toàn tuyến ở mục 1.

Các bài DE kiểm tra Draft-07, range/identity, giới hạn payload, receipt ledger, replay xung đột, DLQ, lỗi FK riêng dòng, binding Arduino/gateway, đồng hồ chưa đồng bộ, công tơ đến muộn/reset và registry trùng. BatchStore trực tiếp → PostgreSQL 16 cũng lưu 10.000/10.000 trong 6,171 giây (1.620,54/s); con số này không được dùng thay benchmark MQTT ở trên.

Ruff runtime checks PASS. Log được kèm trong evidence/w5-tests.txt.

## 3. Kết quả local trước đây của người phụ trách

Người dùng đã cung cấp log Windows/Docker của phiên bản DE trước: 10.000/10.000 trong 6,07 giây, 1.647,33/s; demo/DLQ/replay đúng; sáu job Success và tám dòng điện năng khớp raw. Đây là lịch sử, tách biệt với kết quả mới ở mục 1.

## 4. Đối chiếu Jira

| Yêu cầu | Phần đã hoàn thành | Phần nghiệm thu còn lại |
| --- | --- | --- |
| DDL G1, hai hypertable | Giữ DDL, migration và chạy trên TimescaleDB thật | Áp dụng trên VPS nhóm |
| Subscribe telemetry/v1/# | Worker mTLS, QoS 1 ACK sau commit | Firmware/thiết bị thật kết nối |
| JSON Schema v7 và DLQ | Đã kiểm thử đúng/sai/replay | Đối chiếu payload thực |
| Batch >500 records/s | MQTT → TimescaleDB đạt 1.259,12/s | Đo lại trên cấu hình Staging |
| Aggregate tự cập nhật đúng | 8/8 bucket khớp, scheduler thực | Đối chiếu dữ liệu điện năng vật lý |
| 100% bản tin ESP32 | Có receipt ledger và reconcile.py | Cần manifest nguồn ESP32 thật |

## 5. Phạm vi chưa có bằng chứng vật lý

Chưa có VPS/SSH/DNS và thiết bị vật lý trong phiên làm việc này. Chưa chạy stack Docker mục tiêu, chưa đo uptime 24/7, chưa flash ESP32 hoặc đo điện/quang học. Nhánh ESP-IDF mới của nhóm vẫn ở S1 scaffold; firmware Arduino cũ còn QoS 0 và số đo mô phỏng.

Không đánh dấu SCRUM-29 Done chỉ từ nộp mã. Sau khi cấp host/thiết bị, triển khai bằng bộ TL đã cung cấp, điền registry thật, ghi manifest phát và chạy đối soát 100% trong khoảng nghiệm thu. Nhãn measured của simulator không phải phép đo phần cứng.
