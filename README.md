# PCCOM · Mẫu cấu hình Technical Lead & DevOps

## Chạy thử MQTT 5 và API mTLS

Chuẩn bị Linux hoặc WSL2, Docker với Compose v2, OpenSSL 3 và curl. Giải nén
trên hệ thống tệp Linux (ví dụ thư mục cá nhân trong WSL) để giữ quyền 0600.
Cổng 8883 và 8443 chỉ bind ở loopback. Dùng tài nguyên chạy thử và dữ liệu giả lập.
Mở `contracts/README.md` để xem schema JSON và dữ liệu mẫu cho telemetry,
receipt, command, ACK và manifest.

## 📌 Project Overview
An integrated IoT and cloud platform designed to monitor and manage outdoor smart lighting infrastructure and outdoor LED digital signage networks. The system integrates real-time telemetry, AI/ML-driven adaptive dimming, predictive anomaly detection, energy analytics, and secure multi-tier content publishing workflows with resilient edge offline fallback.

---

## 👥 Scrum Team Structure & Roles (10 Members)

| Role | Member / Lead | Primary Responsibilities |
| :--- | :--- | :--- |
| **Product Owner (PO) & Team Leader** | **Bạn (Role cao nhất)** | Quản lý Product Goal, độ ưu tiên Product Backlog, liên lạc & nghiệm thu với doanh nghiệp PCCOM, ra quyết định bàn giao các mốc (G0 - G4). |
| **Scrum Master (SM)** | Thành viên 2 | Tối ưu hóa quy trình Scrum, điều phối các buổi họp (Daily, Sprint Planning, Review, Retrospective), tháo gỡ khó khăn cho team. |
| **Technical Lead & DevOps Developer** | Thành viên 3 | Thiết kế kiến trúc tổng thể, hạ tầng CI/CD, chuẩn bảo mật (ASVS, SEC 01-05), quản lý cấu hình triển khai Cloud/Edge. |
| **IoT & Edge Developer** | Thành viên 4 | Lập trình gateway/controller thiết bị, giao thức MQTT 5 / DALI / D4i, thuật toán local fallback, bộ đệm offline (OPS 02). |
| **Data Engineering Developer** | Thành viên 5 | Xây dựng pipeline dữ liệu đo lường (telemetry), lưu trữ Time-Series, tiền xử lý, kiểm soát chất lượng dữ liệu (Annex C). |
| **ML Developer 1 (Adaptive Lighting)** | Thành viên 6 | Huấn luyện và triển khai mô hình điều khiển ánh sáng thích ứng (AI 01), phân tích tối ưu hóa tiêu thụ năng lượng (AI 03). |
| **ML Developer 2 (Anomaly Detection & Eval)** | Thành viên 7 | Xây dựng mô hình phát hiện bất thường thiết bị/mạng lưới (AI 02), kiểm thử độ chính xác (Precision ≥85%, Recall ≥90% - AT 06). |
| **Backend Developer** | Thành viên 8 | Xây dựng lõi Core API, quản lý trạng thái thiết bị, phân quyền RBAC/MFA, workflow duyệt và phân phối nội dung LED đa cấp (DSP 02-04). |
| **Frontend Developer** | Thành viên 9 | Phát triển Web Console điều hành trung tâm, bản đồ GIS vị trí đèn/LED, trình quản lý nội dung số CMS và báo cáo phân tích. |
| **QA Engineering Developer** | Thành viên 10 | Thiết lập kiểm thử tự động (AT 01 - AT 12), quản lý ma trận truy vết (RTM), kiểm thử tải (NFR 01), mô phỏng sự cố mất mạng/nguồn. |

---

## 🗓️ Delivery Roadmap & Acceptance Gates (16 Weeks)
- **G0 (Week 2):** Readiness & First Slice – Nghiệm thu khảo sát, kiểm tra bench test phần cứng/driver, pipeline CI/CD và kết nối Jira/Git.
- **G1 (Week 4):** Design Approval – Phê duyệt kiến trúc, mô hình bảo mật, chuẩn dữ liệu (schemas), backlog và giao thức đo sáng.
- **G2 (Week 8):** Integrated Pilot – Trình diễn hệ thống tích hợp (Lighting + Display + Edge Fallback).
- **G3 (Week 14):** Acceptance Dossier – Hoàn thiện hồ sơ nghiệm thu kỹ thuật, chứng chỉ bảo mật và báo cáo AI/ML sau 30 ngày quan sát.
- **G4 (Week 16):** Handover & Transfer – Chuyển giao toàn bộ mã nguồn, tài liệu vận hành và đào tạo cho PCCOM CO., LTD.

---

## 🛠️ Project Structure
```text
├── docs/                   # Tài liệu yêu cầu, báo cáo tuần, kiến trúc
│   ├── specifications/     # Đặc tả giao thức, nghiệp vụ, quy chuẩn an toàn
│   ├── test_reports/       # Báo cáo kiểm thử E2E/LWT kèm số đo thực tế
│   └── weekly_reports/     # Báo cáo tiến độ hàng tuần nộp LMS (Week 02, Week 03,...)
├── src/
│   ├── iot_protocol/       # Topic taxonomy, HMAC, User Properties, MQTT 5 helpers
│   ├── lighting_control/   # DALI, Fade, Thermal Derating, Offline Fallback (Python core)
│   ├── edge_simulator/     # Virtual Edge Simulator MQTT 5 (đèn/LED/gateway)
│   ├── backend/            # Mock Cloud Service & Core API
│   ├── firmware_esp32/     # Firmware gateway/controller ESP32 + C++ lighting modules
│   └── frontend/           # Web Console & GIS Dashboard
├── tests/                  # Unit test giao thức và cấu hình simulator
└── tools/                  # Probe MQTT 5, script Jira, tạo repo GitHub
```

## 💡 Lighting Control Modules and Safety Supervisor
- Python core: [`src/lighting_control/README.md`](src/lighting_control/README.md)
- ESP32 C++ headers: `src/firmware_esp32/include/lighting_control/`
- ESP32 C++ implementations: `src/firmware_esp32/src/lighting_control/`
- Unit tests `Lighting Control Modules`: `tests/test_lighting_control.py`
- **Safety Supervisor:** `src/lighting_control/safety/` (Python) và `src/firmware_esp32/{include,src}/lighting_control/` (C++). Tài liệu: [`src/lighting_control/safety/README.md`](src/lighting_control/safety/README.md).
- Unit tests `Safety Supervisor` : `tests/test_safety_supervisor.py`; C++ host harness: `tests/cpp/test_safety_supervisor.cpp`.
- Lưu ý: Safety Supervisor đã được triển khai và kiểm thử độc lập, nhưng chưa được nối vào `main.cpp`. Firmware `main.cpp` vẫn là luồng PWM cũ cho đến khi hoàn tất tích hợp, đặc tả đường cong và adapter/transceiver DALI thực tế. Các module mới chưa được coi là nghiệm thu điều khiển DALI trên phần cứng.

## 🔌 MQTT 5 Protocol & Simulator
- Đặc tả giao thức: [`docs/specifications/MQTT5_COMMUNICATION_PROTOCOL.md`](docs/specifications/MQTT5_COMMUNICATION_PROTOCOL.md)
- Hướng dẫn simulator: [`src/edge_simulator/README.md`](src/edge_simulator/README.md)
- Báo cáo E2E/LWT: [`docs/test_reports/MQTT5_E2E_REPORT.md`](docs/test_reports/MQTT5_E2E_REPORT.md)
- Quyết định topic Phương án C + bridge: [`docs/proposals/TOPIC_ALIGNMENT.md`](docs/proposals/TOPIC_ALIGNMENT.md)
- Changelog: [`docs/CHANGELOG.md`](docs/CHANGELOG.md)

Chạy nhanh với broker công cộng:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item config.example.json config.json
.\.venv\Scripts\python.exe src\edge_simulator\virtual_lighting_network.py --max-devices 5

`

### Chạy Lab Kiểm thử Kiến trúc & An ninh mạng (mTLS & Cloud Smoke Test):
`ash
```bash
bash lab/generate-pki.sh
docker compose --env-file lab/compose.env -f lab/compose.yml up -d
bash lab/smoke.sh
docker compose --env-file lab/compose.env -f lab/compose.yml down -v
`
```

`generate-pki.sh` tạo CA server, CA gateway và CA dịch vụ cùng các chứng chỉ
ngắn hạn. Các CA này chỉ dành cho lab. File sinh trong `lab/generated/` chứa
khóa riêng và được bỏ qua khi commit. Nếu tạo lại, hãy dừng Compose và chuyển
thư mục `lab/generated/` ra một vị trí kiểm thử mới trước khi chạy lại.

`lab/smoke.sh` kiểm tra API có serial đã đăng ký và MQTT 5 phân quyền topic.
Listener MQTT 8883 dành cho thiết bị. Listener 8884 dành cho dịch vụ và chỉ
truy cập trong mạng Compose. API chỉ có `GET /v1/edge/health` mô phỏng.
Các phần kiểm chữ ký lệnh, nhật ký thực thi, chấp thuận theo tenant/site,
thu hồi phiên đang chạy và adapter phần cứng được đặc tả trong SAD để tích hợp.

## Phạm vi đã kiểm tra

Cấu hình MQTT và NGINX đã được chạy cục bộ với Mosquitto 2.0.21,
NGINX 1.26.3 và OpenSSL 3.5.7. MQTT 5 cho phép gateway ghi vào topic được cấp
và dispatcher phát lệnh. Broker chặn ghi vào site khác, chặn gateway ghi lệnh
và giữ phiên của gw-002 khi gw-001 tự gửi client ID trùng. API cho phép
certificate đã đăng ký. Các trường hợp sai CA, sai hostname, thiếu cert
và cert đã thu hồi bị từ chối tại đầu nối. Với API, cert đúng CA nhưng chưa
đăng ký cũng bị từ chối.

Chạy lại `lab/smoke.sh` với phiên bản ảnh Compose đã khóa digest trong Dev.
Dùng ma trận kèm theo để kiểm tra đầy đủ quyền subscribe, thu hồi phiên đang mở,
xác thực Registry trên broker, chữ ký lệnh và fallback trên Staging.

## Kết nối GitHub Actions

1. Tạo hai GitHub Environments đúng tên `dev` và `staging`. Giới hạn nhánh
   `develop` vào Dev và `release/staging` vào Staging. Bảo vệ hai nhánh và
   yêu cầu review các tệp workflow, cấu hình IAM, bản phát hành.
2. Yêu cầu người khác duyệt triển khai Staging và bật Prevent self-review
   khi gói GitHub hỗ trợ. Nếu repo private chưa có Required reviewers, dùng
   phê duyệt tại pull request để cập nhật nhánh `release/staging` được bảo vệ
   hoặc cổng phê duyệt đã được dự án chấp nhận.
3. Trong mỗi tài khoản AWS, thêm GitHub OIDC provider và tạo một deployment
   role riêng. Điền mẫu `ops/iam/oidc-trust.json` bằng `sub` chính xác
   của repo và môi trường thực tế. Repo có thể dùng định dạng có ID bất biến
   hoặc cấu hình tùy chỉnh. Kiểm tra claim thực tế và giữ điều kiện `StringEquals`.
   Điền `ops/iam/ecs-deploy.json` theo service và family của từng môi trường.
4. Đặt các GitHub Environment Variables `AWS_ACCOUNT_ID`, `AWS_REGION`,
   `AWS_ROLE_ARN`, `ECS_CLUSTER` và `ECS_SERVICE`. Đây là cấu hình triển khai.
   Cấp quyền đọc secret cho task role của ứng dụng theo ARN dưới
   `/pccom/dev/` hoặc `/pccom/staging/`. Đặt secret trong AWS Secrets Manager.
5. Đăng ký ECS task definition từ quy trình build đã duyệt, dùng image theo
   digest và đúng family `pccom-core-dev` hoặc `pccom-core-staging`. Đặt ARN đã
   duyệt vào `ops/releases/<environment>.task-arn`. Thay các giá trị mẫu trước
   khi triển khai. Cấu hình ECS rolling deployment, circuit breaker có rollback
   và health check. Job deploy cập nhật một service có sẵn và xác nhận revision
   PRIMARY đã hoàn tất, kể cả khi ECS tự quay về bản cũ.
6. Dev chạy sau push vào `develop`. Staging chạy bằng Run workflow với nhánh
   `release/staging` và target `staging`. Kiểm tra API, MQTT, DB read/write và
   audit trong môi trường đích theo kế hoạch QA. Thu lại run ID và task ARN.
   Để rollback chủ động, đưa ARN trước đó đã duyệt vào file môi trường tương ứng qua nhánh được bảo vệ rồi chạy lại workflow. Đảm bảo schema tương thích.

`lab-ci.yml` chạy kiểm thử Compose, độc lập với quyền truy cập Cloud. Trước khi dùng trong Staging, cập nhật image/tag thành digest đã rà soát và ghi phiên bản
OpenSSL, broker, proxy, AWS CLI vào bằng chứng chạy. Gói mẫu chưa mang thông tin tài khoản, cấu hình thiết bị thật hoặc quyền triển khai.

- [Eclipse Mosquitto](https://mosquitto.org/man/mosquitto-conf-5.html)
- [NGINX SSL module](https://nginx.org/en/docs/http/ngx_http_ssl_module.html)
- [GitHub Actions OIDC](https://docs.github.com/en/actions/reference/security/oidc)
- [AWS IAM role cho GitHub OIDC](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-idp_oidc.html)
