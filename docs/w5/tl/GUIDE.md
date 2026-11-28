# SCRUM-26 / W5-TL — Hướng dẫn triển khai và nộp mã

Ngày: 27/11/2026. Đích triển khai đã chọn: VPS/Linux + Docker Compose.

## 1. Phạm vi gói

Gói bổ sung Compose Staging, Mosquitto mTLS trên 8883, TimescaleDB 2.32/PG17 (image khóa digest), API FastAPI, web HTTPS, Internal PKI, các workflow PR, Prometheus/Grafana/Loki/Alloy/cAdvisor/Portainer và công cụ lấy bằng chứng.

API Staging tái sử dụng lớp auth/session của SCRUM-30, bổ sung console API có scope tenant/site, command outbox và xác nhận bằng telemetry. DE là dịch vụ duy nhất ghi telemetry. Không chạy mock_cloud_service làm worker Staging.

## 2. Nguồn và phụ thuộc

- Main: 817aeb30dc1454dc704f92f05677cfcaf65971e0.
- W5-DE đã nộp: 9e8a923d0696cd7867ff87f68bdeb85ae9d0a838, được nâng cấp trong gói DE.
- Auth Backend SCRUM-30: b328755a84d873ab8f1161689b16a39a95f70cc1. Gói chứa các tệp auth cần thiết để không giả định PR #12 đã merge.
- Retain plugin và khung ESP-IDF: Developer-1 dc9a26d1367c694cbfd637ef951eb87afbb0cb23, giữ ghi nhận nguồn trong manifest.
- Giao diện chạy từ gốc repository, do gói FE cung cấp.

Giải nén DE, FE và TL vào **cùng một bản clone** để chạy tích hợp. Không dùng cả ZIP như một tệp mã nguồn trên GitHub.

Nộp thủ công: tạo nhánh feature/w5-tl-staging, Add file → Upload files tại gốc repo, kéo nội dung gói giữ nguyên các đường dẫn. Các tệp .github và .gitignore cũng phải được tải lên; bật hiển thị tệp ẩn trên Windows. Commit gợi ý: SCRUM-26: add integrated staging and PR pipeline.

Khi phân nhánh riêng, tích hợp DE và FE vào nhánh chung trước khi chạy bộ CI TL đầy đủ. Chưa đủ nguồn phụ thuộc thì lỗi build không phải bằng chứng triển khai hoàn chỉnh. Không cần tự merge main để nộp mã; người review của nhóm quyết định tích hợp.

## 3. Chuẩn bị VPS

Cần Linux, Docker Engine/Compose, Python 3, OpenSSL, DNS/IP thực tế và quyền quản trị máy. Hiện chưa có địa chỉ VPS hoặc quyền SSH được cung cấp; bộ mã này chưa triển khai vào máy chủ của nhóm.

Đã có script chuẩn bị host Ubuntu/Debian. Sau khi đặt ba gói trong checkout trên VPS được cấp, chạy:

~~~bash
sudo bash tools/staging/install-host.sh
~~~

Script cài công cụ và bật Docker khi khởi động máy. Các lệnh vận hành dưới đây dùng sudo; script không tự mua/tạo VPS hoặc đổi firewall SSH của nhóm.

- Dành 443/TCP cho web HTTPS và 8883/TCP cho MQTT mTLS.
- Database và API không publish ra Internet.
- Grafana 3000, Prometheus 9090 và Portainer 9443 chỉ bind 127.0.0.1.
- Kiểm tra các cổng 443/8883 chưa bị lab khác chiếm trước khi chạy.
- Docker cần tự khởi động cùng máy; dùng volume giữ database, MQTT và dữ liệu giám sát.

## 4. Chuẩn bị source và registry thật

Đặt repository đã ghép ba gói tại /opt/pccom hoặc sửa WorkingDirectory trong unit systemd theo nơi thực tế.

~~~bash
cd /opt/pccom
python3 -m venv .venv-tools
.venv-tools/bin/pip install jsonschema==4.25.1
cp deploy/staging/registry.example.json devices.json
~~~

Điền devices.json theo hướng dẫn DE. UUID, firmware, tọa độ và mã MQTT phải do nhóm xác nhận. Mỗi mục là một thiết bị; không dùng dữ liệu DEMO cho nghiệm thu thật.

~~~bash
.venv-tools/bin/python tools/staging/bootstrap.py --host YOUR_ACTUAL_HOST --registry devices.json
~~~

YOUR_ACTUAL_HOST là tên miền hoặc IP trần, không có https:// hay số cổng. SAN certificate có hostname này và tên nội bộ mosquitto. Script tạo .staging riêng tư và từ chối ghi đè nếu nó đã tồn tại.

## 5. Chứng chỉ và bí mật

- .staging/ca/ca.key là khóa CA; không mount vào container và không đưa lên Git.
- .staging/certificates.json ánh xạ thiết bị/gateway sang thư mục chứng chỉ.
- Mỗi ESP32 nhận đúng ca.crt, client.crt và client.key của nó qua kênh riêng.
- Web Gateway, worker và healthcheck có chứng chỉ tách biệt và ACL riêng.
- Mật khẩu DB/API/JWT/operator/Grafana được sinh ngẫu nhiên, không có mật khẩu mặc định trong gói.
- Thư mục runtime trên host có quyền 0700. Các tệp secret được bind riêng và chỉ đọc để UID dịch vụ trong container truy cập được; không dựa vào tùy chọn uid/gid của Compose file-secret.

Đây là PKI Staging mới, không tự động tin cậy chứng chỉ lab generated/ cũ. Cấp chứng chỉ mới cho IoT theo mapping; không trộn hai CA.

Auth sử dụng một tài khoản pilot staging-operator theo cơ chế bootstrap của SCRUM-30; mật khẩu nằm tại .staging/secrets/operator_password. Quản lý nhiều tài khoản/SSO không thuộc bộ này.

## 6. Khởi động

~~~bash
sudo bash tools/staging/deploy.sh
~~~

Script kiểm tra Compose, build ba image API/web/broker và đợi healthcheck. Migration chạy DDL G1 một lần, thêm bảng vận hành, đăng ký thiết bị và cấp quyền DB tách biệt cho API/ingestion.

Truy cập https://YOUR_ACTUAL_HOST/. Cài CA nội bộ vào máy kiểm thử để xác minh certificate đúng cách. Không tắt xác minh TLS của MQTT khi gặp lỗi tên miền hoặc CA.

Nếu dùng unit systemd:

~~~bash
sudo install -m 644 deploy/staging/pccom-staging.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pccom-staging
~~~

Sửa đường dẫn unit trước nếu clone không ở /opt/pccom. restart policy xử lý container lỗi; systemd đưa stack lên sau reboot. Muốn khẳng định online 24/7 vẫn cần theo dõi uptime thật.

## 7. Monitoring và log

Từ máy cá nhân tạo SSH tunnel với địa chỉ VPS thực:

~~~bash
ssh -L 3000:127.0.0.1:3000 -L 9090:127.0.0.1:9090 -L 9443:127.0.0.1:9443 USER@VPS
~~~

- Grafana: http://127.0.0.1:3000, user staging-admin, mật khẩu trong secret tương ứng.
- Dashboard PCCOM Staging: API/MQTT, số receipt/DLQ, CPU/RAM container và log.
- Prometheus: http://127.0.0.1:9090.
- Portainer: https://127.0.0.1:9443; hoàn thành thiết lập admin khi mở lần đầu.
- Loki/Alloy thu log từ Docker; proxy chỉ cho các API đọc cần thiết, không cho POST.

Portainer có quyền quản trị Docker; chỉ dùng qua tunnel/tài khoản quản trị. cAdvisor cần quyền đọc host và privileged để lấy chỉ số container.

## 8. Kiểm thử tích hợp trên máy Docker riêng

Dùng một checkout/môi trường thử sạch, chưa có .staging hoặc dữ liệu thật:

~~~bash
.venv-tools/bin/python tools/staging/bootstrap.py --host localhost --demo
sudo bash tools/staging/deploy.sh
sudo docker compose --env-file .staging/compose.env -f docker-compose.staging.yml -f docker-compose.staging.test.yml run --rm verify
sudo bash tools/staging/evidence.sh
~~~

Đầu ra verify chỉ PASS khi: mTLS hoạt động, không cert bị từ chối, health identity không được publish telemetry, demo/DLQ/replay đúng, 10.000 bản tin MQTT lưu đủ và >500/s, aggregate giờ tự cập nhật khớp raw, dimming riêng/nhóm có telemetry mới xác nhận.

Để kiểm thử scheduler nhanh, verify tạm đổi schedule hai job giờ thành 5 giây rồi khôi phục trong finally; không gọi refresh thủ công. Đây vẫn là dữ liệu mô phỏng, không phải HIL.

### Chạy tích hợp native khi máy kiểm thử không có Docker

Bộ bàn giao này đã chạy PASS bằng Mosquitto 2.0.22, PostgreSQL 17.11 và TimescaleDB 2.32.0 thật; benchmark MQTT đạt 1.259,12/s và browser xác nhận dimming riêng/nhóm. Kết quả chi tiết trong TEST_REPORT.md và evidence/. Kiểm thử native không thay cho việc chạy image, Nginx, monitoring hoặc VPS.

Muốn chạy lại, cần cài đúng PostgreSQL/TimescaleDB vào cùng distribution, Mosquitto kèm header phát triển, C compiler, OpenSSL, Node 24 và Python 3.12. Chạy bằng user thường vì initdb không cho chạy root:

~~~bash
python3 -m venv .venv-test
.venv-test/bin/pip install -r requirements-native-test.txt playwright==1.65.2
.venv-test/bin/python -m playwright install chromium
npm ci
npm run build
.venv-test/bin/python tools/staging/native_acceptance.py --pg-bin /path/to/postgresql/bin --mosquitto /path/to/mosquitto --mosquitto-include /path/to/mosquitto/include --runtime /tmp/pccom-native --browser
~~~

Thay ba đường dẫn theo cài đặt thực; header cần mosquitto.h, mosquitto_broker.h và mosquitto_plugin.h. Runner tạo database/PKI dùng một lần, bind loopback, chạy migration/broker/API/worker, gửi dữ liệu DEMO, mở Chromium rồi dọn tiến trình. Thư mục runtime còn log và khóa thử nghiệm; không tải nó lên Git.

## 9. CI/CD

Workflow w5-staging.yml chạy trên mọi pull_request:

1. Ruff, kiểm thử PostgreSQL và các unit test giao thức sẵn có.
2. npm ci, test, typecheck/build và smoke test trình duyệt → API → PostgreSQL.
3. PlatformIO build Arduino esp32dev và ESP-IDF esp32_dev; không flash hoặc burn eFuse.
4. Build Docker API/worker/web/broker rồi chạy bộ kiểm thử MQTT/Timescale trong Compose.
5. Lưu bằng chứng không chứa secret và dọn môi trường CI dùng một lần.

Workflow được cung cấp, nhưng chưa chạy trên GitHub cho bộ thay đổi này. Chỉ ghi “CI thành công” sau khi có run thật và link log. CI không tự SSH/deploy lên một VPS chưa được cấu hình.

## 10. Phối hợp IoT và nghiệm thu

Nhánh Developer-1 mới có lab mTLS S0 và scaffold ESP-IDF S1; main.c hiện chỉ chạy vòng lặp log. IoT cần hoàn thiện S2: Wi-Fi/NTP, mTLS, MQTT 5, telemetry và xử lý lệnh theo hợp đồng; sau đó mới flash, đo và cung cấp manifest phát.

Firmware Arduino cũ còn broker công cộng/1883, QoS 0 và số đo mô phỏng. Không xem build Arduino là bằng chứng ESP32 đã kết nối Staging.

Chốt SCRUM-26 khi VPS online thật, 443/8883 được kiểm tra từ ngoài, chứng chỉ ESP32/Web Gateway hoạt động, dashboard/log có dữ liệu và tất cả job PR thành công. Chốt DE/FE cùng QA sau đối soát thiết bị và thử dimming thực.
