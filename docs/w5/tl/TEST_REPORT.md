# SCRUM-26 / W5-TL — Báo cáo kiểm thử

Ngày: 27/11/2026. Đã hoàn thành mã triển khai, Internal PKI, monitoring và CI; đã kiểm thử tích hợp phần mềm với broker/TimescaleDB thật. Chưa có bằng chứng Cloud online 24/7 hoặc GitHub Actions run cho bộ thay đổi này.

## 1. Truy cập và nguồn

GitHub đọc được: đã lấy 13 nhánh và lập danh mục 301 blob duy nhất, gồm 286 tệp văn bản, 10 DOCX đọc trích xuất được, 1 DOCX placeholder không hợp lệ và 4 tệp nhị phân. SAD_Technical_Architecture.docx chỉ có một ký tự xuống dòng. Ba mô hình ML và hero.png được kiểm tra metadata, không thực thi mô hình; không xem đây là kiểm toán nội dung mọi nghiệp vụ. Danh mục/hash trong docs/w5/repository-review.json.

Jira chuyển tới trang đăng nhập Atlassian. Yêu cầu dựa trên ba ảnh SCRUM-26/29/31 và RFP 29 trang đã đọc. Developer-1 dc9a26d và QA 1b0feaa đã được lập danh mục; không tự merge nhánh QA. Auth được tái sử dụng từ SCRUM30 b328755, retain plugin và scaffold IDF từ Developer-1, có ghi nguồn trong manifest.

## 2. Kết quả đã thực hiện

| Kiểm tra | Kết quả |
| --- | --- |
| Mosquitto 2.0.22 khởi động với config/plugin Staging | PASS, chỉ listener TLS thử nghiệm, không mở thêm 1883 |
| mTLS client hợp lệ; client thiếu cert | PASS kết nối / PASS từ chối |
| ACL health identity không được publish telemetry | PASS |
| OpenSSL purpose server/client, hostname và quyền PKI | PASS |
| Bootstrap từ chối ghi đè runtime PKI | PASS |
| PostgreSQL 17.11 + TimescaleDB 2.32.0, nguyên DDL G1 | PASS, hai hypertable/sáu aggregate |
| MQTT → worker → TimescaleDB | 10.000/10.000, 7,942 giây, 1.259,12/s |
| Aggregate giờ chạy theo scheduler | 8 bucket khớp raw, 0 sai lệch |
| Sáu policy sau bài thử | Bật, lần gần nhất Success; lịch giờ đã trả về 15 phút |
| API đăng nhập, scope và lệnh dimming riêng/nhóm | PASS |
| Chromium → API → MQTT → worker → TimescaleDB → Web | PASS, simulator thiết bị, không mock dispatcher |
| 16 bài pytest mới | PASS: 8 DE + 5 API + 2 PKI/config + 1 browser |
| 90 unit test giao thức/safety sẵn có | PASS |
| Frontend 4 unit test, strict TypeScript và production build | PASS |
| Ruff runtime checks; bash syntax ba script host/deploy/evidence | PASS |
| YAML/build paths/mounts/public ports của Compose | PASS kiểm tra cấu hình |
| Giải nén ba ZIP lên main sạch, đối chiếu hash | PASS; 15 test PASS/1 browser skip trong checkout mới, 4 FE test và build PASS |

Kiểm thử toàn tuyến dùng các tiến trình Linux native với cùng phiên bản thành phần mục tiêu, không có Docker daemon. Không suy ra các image, Nginx, monitoring hoặc VPS đã được chạy từ kết quả này. Bài pytest PostgreSQL 16 có dispatcher được điều khiển là bài riêng; bài native toàn tuyến sử dụng MQTT thực và scheduler Timescale thực.

Bằng chứng native-acceptance.txt/native-result.json ghi rõ môi trường, phiên bản, job và sáu lệnh verified. Thiết bị phát dữ liệu là simulator có nhãn DEMO. Công cụ native_acceptance.py tái tạo môi trường dùng một lần và dọn tiến trình sau khi chạy.

Image TimescaleDB đã khóa theo digest của manifest được đối chiếu để giữ PostgreSQL 17.11. Metadata trong evidence/image-target-metadata.json; xác minh manifest các image trong evidence/image-manifests.json chỉ chứng minh tag truy cập được, không thay cho Docker build/run.

## 3. Các lỗi tích hợp đã xử lý

- Đặt per_listener_settings trước cấu hình bảo mật và đặt plugin bên trong listener TLS. Kiểm tra runtime ngăn listener 1883 ngoài ý muốn.
- Chuyển nhận ACK lệnh sang hàng đợi: callback MQTT không chờ database đang bị transaction outbox khóa, tránh kẹt PUBACK khi gửi nhóm. Có regression test và bài dimming nhóm toàn tuyến.
- Sửa dependency pg8000>=3.2 không tồn tại; dùng psycopg đã kiểm thử.
- Thêm jti cho refresh token rotate trong cùng giây.
- API và ingestion dùng DB role riêng; không chạy mock_cloud_service hoặc MQTT broker công cộng trong Staging.
- Secrets được sinh runtime, CA key không mount, admin UI bind loopback.
- Bản đồ/biểu đồ FE tải riêng, chunk khởi tạo còn khoảng 104,74 KB gzip.

## 4. Chưa chạy và không ghi PASS

- Docker build/run các image mục tiêu và Docker daemon trên VPS; host installer mới được kiểm tra cú pháp.
- Nginx HTTPS, Prometheus/Grafana/Loki/Alloy/cAdvisor/Portainer trong runtime Docker.
- GitHub Actions cho thay đổi mới; chỉ có workflow, chưa có run/link CI.
- Firmware build lần này: tải toolchain PlatformIO chưa hoàn tất, không có log SUCCESS. Workflow có Arduino và ESP-IDF dev target, không flash/burn eFuse.
- Cloud/VPS uptime 24/7, kiểm tra WAN 443/8883, reboot và ESP32/HIL.

Nhánh IoT cung cấp LAB_S0_VALIDATION.md và FIRMWARE_S1_VALIDATION.md báo cáo mTLS lab và build S1 của tác giả. Hai tệp giữ nguyên và ghi nguồn; không dùng làm kết quả do bộ mã này mới tạo ra. main.c S1 chưa có MQTT/telemetry/HMAC.

## 5. Đối chiếu tiêu chí Jira

| Tiêu chí | Hiện trạng |
| --- | --- |
| Compose Mosquitto mTLS + TimescaleDB + FastAPI | Cấu hình/migration/PKI đã viết; ba thành phần đã chạy tích hợp native |
| Client cert ESP32 và Web Gateway | Công cụ cấp riêng đã kiểm thử; Web Gateway kết nối mTLS thật; ESP32 chưa nạp |
| PR build firmware/backend/worker và test | Workflow đủ các job, chưa có GitHub run |
| Monitoring/log aggregation | Đủ cấu hình và dashboard, chưa chạy Docker runtime |
| Cloud online 24/7 | Chưa có VPS được cấp để triển khai/đo |
| CI thành công 100% mỗi PR | Chưa có bằng chứng run |

SCRUM-26 có bộ triển khai cụ thể, không phải chỉ tài liệu kế hoạch. Chỉ chốt Done sau khi triển khai host được cấp, lấy log uptime/WAN/monitoring và link CI thực. Không phải đợi một người khác viết lại phần TL.

## Nguồn kỹ thuật

- [Docker Compose secrets](https://docs.docker.com/compose/how-tos/use-secrets/)
- [Docker Compose startup order](https://docs.docker.com/compose/how-tos/startup-order/)
- [Grafana Alloy Docker log source](https://grafana.com/docs/alloy/latest/reference/components/loki/loki.source.docker/)
- [Mosquitto configuration](https://mosquitto.org/man/mosquitto-conf-5.html)
