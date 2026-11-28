# BÁO CÁO TIẾN ĐỘ HỌC KỲ DOANH NGHIỆP - TUẦN 05
## GIAI ĐOẠN: SPRINT 3 (TUẦN 5/6) — TRIỂN KHAI HẠ TẦNG CLOUD STAGING, FIRMWARE ESP32 & CORE PIPELINE HƯỚNG TỚI GATE G2

---

### THÔNG TIN CHUNG HỌC PHẦN & DỰ ÁN
- **Cơ sở đào tạo:** Trường Đại học Giao thông Vận tải TP.HCM (UTH) — Khoa Công nghệ Thông tin
- **Học phần:** Đồ án Học kỳ Doanh nghiệp (Enterprise Semester Capstone)
- **Doanh nghiệp đồng hành & Thẩm định:** CÔNG TY TNHH KỸ THUẬT TIN HỌC PHÚC CHÂU (PCCOM CO., LTD)
- **Giảng viên hướng dẫn:** HÀN TRUNG ĐỊNH
- **Đề tài:** Intelligent Lighting and Outdoor LED Display Monitoring and Control (Hệ thống giám sát và điều khiển chiếu sáng thông minh & màn hình LED ngoài trời)
- **Giai đoạn:** Tuần 05 (Mở đầu Sprint 3, từ 25/11/2026 đến 01/12/2026)
- **Cột mốc mục tiêu:** **Gate G2 Integrated Pilot** (Tích hợp phần cứng ESP32 với Driver LED DALI/0-10V, thông luồng Telemetry MQTT 5 lên Cloud Staging, Core REST API & Ingestion TimescaleDB)
- **Jira Cloud:** `https://hockidoanhnghiep.atlassian.net` (Project Key: `SCRUM`, Sprint 3 ID: `4`)
- **GitHub Repository:** `https://github.com/Trng-Ngyn/Intelligent-Lighting-and-Outdoor-LED-Display-Monitoring-and-Control`

---

## 1. TỔNG KẾT TIẾN ĐỘ TUẦN 05 (SPRINT 3 — TUẦN ĐẦU)

### 1.1. Đánh giá tiến độ theo Sprint Goal
Trong Tuần 05, nhóm đã đóng hoàn toàn Sprint 2 (11/11 tasks Done, nghiệm thu Gate G1) và khởi động mạnh mẽ Sprint 3 với **6/10 hạng mục kỹ thuật cốt lõi đã hoàn tất và merge lên nhánh chính `main`**:
- **Nghiệm thu Gate G1 & Chuẩn bị Lab (`SCRUM-22`, `SCRUM-24`):** Hoàn tất hồ sơ kiểm thử chấp nhận `ATP_GATE_G1_v0.2.md`, ma trận `RTM_G1_v0.4.xlsx`, và bộ kiểm thử tự động CI (`PR #13`); chốt danh mục linh kiện Lab BOM cho thử nghiệm HIL.
- **Hạ tầng Cloud Staging & Giám sát (`SCRUM-26`, `PR #14`):** Thiết lập trọn bộ `docker-compose.staging.yml`, Dockerfile cho API/MQTT/Web, cấu hình Mosquitto TLS, Nginx, hệ thống giám sát Prometheus + Grafana + Loki + Alloy.
- **Firmware ESP32 ESP-IDF mTLS MQTT 5 (`SCRUM-27`, nhánh `Developer-1`):** Hoàn thiện project `src/firmware_esp32_idf/` trên nền ESP-IDF 5.4 / FreeRTOS với 6 module C (`main.c`, `pccom_nvs.c`, `pccom_provision.c`, `pccom_security.c`, `pccom_telemetry.c`, `pccom_network.c`) và profile bảo mật NVS/TLS 1.3.
- **MQTT Ingestion & TimescaleDB (`SCRUM-29`, `PR #15`):** Xây dựng dịch vụ `src/ingestion/worker.py` (488 dòng), adapters, registry, `sql/w5_ingestion.sql`, `docker-compose.w5.yml` và bộ test `tests/w5/test_ingestion.py`.
- **Core REST API FastAPI (`SCRUM-30`, `PR #12`):** Triển khai cấu trúc Clean Architecture trong `src/backend/app/` gồm xác thực JWT/RBAC (`security.py`, `auth.py`), kết nối CSDL (`db.py`), và các router `assets.py`, `controls.py`, `analytics.py`.
- **AI Inference Microservice (`SCRUM-32`, nhánh `W5-ML`):** Đóng gói mô hình Autoencoder & Isolation Forest thành FastAPI microservice (`app/main.py`, `predictor.py`, `classifier.py`, `model_loader.py`) dự đoán bất thường F01–F04.

### 1.2. Tình trạng cập nhật trên Jira Sprint 3
- Đã hoàn tất đóng **Sprint 2** (11/11 tasks `Done`) và kích hoạt **Sprint 3** (`71 Story Points` / `200 Giờ công`):
  - `SCRUM-24` (Trần Đình Trọng - PO): **Done** (Nghiệm thu G1, Lab BOM, Quản trị Backlog & Báo cáo Tuần 5)
  - `SCRUM-25` (Lê Hoàng Thanh - SM): **Done** (Biên bản Sprint Planning 3, DoD Sprint 3, Daily Scrum)
  - `SCRUM-26` (Trần Nhật Hào - TL): **Done** (Hạ tầng Cloud Staging, Monitoring & CI/CD `PR #14`)
  - `SCRUM-27` (Bùi Mai Khánh Kiệt - IoT 1): **Done** (Firmware ESP32 ESP-IDF mTLS MQTT 5 `Developer-1`)
  - `SCRUM-28` (Nguyễn Tấn Vượng - IoT 2): **In Progress** (Đấu nối mạch ESP32 với Driver DALI/0-10V & kiểm thử Fallback)
  - `SCRUM-29` (Lê Tiến Công - DE): **Done** (Ingestion Worker MQTT -> TimescaleDB `PR #15`)
  - `SCRUM-30` (Trần Hoài Nguyên Vỹ - BE): **Done** (Core REST API FastAPI JWT/RBAC `PR #12`)
  - `SCRUM-31` (Đinh Nguyễn Công Bắc - FE): **In Progress** (Tích hợp Web Operations Console React với Staging API)
  - `SCRUM-32` (Đặng Nguyễn Minh Phi - ML): **Done** (Docker Inference Microservice F01-F04 `W5-ML`)
  - `SCRUM-33` (Nguyễn Đại Phước - QA): **In Progress** (Hoàn tất `SCRUM-22` Gate G1; đang chuyển sang HIL Test & Load Test `SCRUM-33`)

---

## 2. BẢNG TỔNG HỢP TIẾN ĐỘ & SẢN PHẨM BÀN GIAO (10 THÀNH VIÊN)

| STT | Thành viên | Vai trò Scrum | Task Jira | Khối lượng hoàn thành trong Tuần 05 | Sản phẩm bàn giao (Deliverables) | Trạng thái |
| :---: | :--- | :--- | :---: | :--- | :--- | :---: |
| 1 | **Trần Đình Trọng** | **Product Owner & Lead** | `SCRUM-24` | Nghiệm thu Gate G1; lập Lab Hardware BOM; giải quyết xung đột & merge PRs (#12–#15) và 3 nhánh (`SM-Sprint3`, `Developer-1`, `W5-ML`) vào `main`. | `GATE_G1_ACCEPTANCE_AND_LAB_BOM_W5.md`; Báo cáo Tuần 05; tích hợp sạch nhánh `main`. | **HOÀN THÀNH** |
| 2 | **Lê Hoàng Thanh** | **Scrum Master** | `SCRUM-25` | Chủ trì Sprint Planning 3; ban hành DoD Sprint 3; thu thập nhật ký Daily Scrum hàng ngày & cập nhật Jira Board. | `BIÊN BẢN SPRINT PLANNING 3.docx`; `definition_of_done_sprint_3.md` (`SM-Sprint3`). | **ĐÃ MERGE MAIN** |
| 3 | **Trần Nhật Hào** | **Technical Lead & DevOps** | `SCRUM-26`<br>*(PR #14)* | Dựng hạ tầng Cloud Staging hoàn chỉnh với Docker Compose, Nginx, Mosquitto TLS, Prometheus, Grafana, Loki & kiểm thử S0/S1 lab. | `docker-compose.staging.yml`; `deploy/staging/`; `docs/w5/tl/TEST_REPORT.md`. | **ĐÃ MERGE MAIN** |
| 4 | **Bùi Mai Khánh Kiệt** | **IoT & Edge Developer 1** | `SCRUM-27` | Xây dựng firmware ESP-IDF 5.4 cho ESP32 (NVS provisioning, mTLS X.509, 3-task MQTT 5 telemetry pipeline, LWT). | `src/firmware_esp32_idf/` (6 modules C, `sdkconfig.defaults.*`, `platformio.ini`). | **ĐÃ MERGE MAIN** |
| 5 | **Nguyễn Tấn Vượng** | **IoT & Edge Developer 2** | `SCRUM-28` | Đấu nối phần cứng ESP32 với mạch Driver LED (DALI / PWM 0-10V) tại phòng Lab và kiểm thử cơ chế bảo vệ nhiệt / Offline Fallback. | Đang hoàn thiện đấu nối & đo kiểm mạch thực tế (dự kiến hoàn tất Tuần 06). | **ĐANG THỰC HIỆN** |
| 6 | **Lê Tiến Công** | **Data Engineer** | `SCRUM-29`<br>*(PR #15)* | Lập trình MQTT Ingestion Worker (`488` dòng), SQL schema `w5_ingestion.sql`, Docker Compose W5 & kiểm thử tích hợp TimescaleDB. | `src/ingestion/worker.py`, `adapters.py`; `sql/w5_*.sql`; `tests/w5/test_ingestion.py`. | **ĐÃ MERGE MAIN** |
| 7 | **Trần Hoài Nguyên Vỹ** | **Backend Developer** | `SCRUM-30`<br>*(PR #12)* | Hiện thực hóa Core REST API bằng FastAPI (`auth`, `assets`, `controls`, `analytics`), phân quyền JWT/RBAC 4 vai trò & kết nối TimescaleDB. | `src/backend/app/` (`main.py`, `db.py`, `core/security.py`, `routers/*.py`). | **ĐÃ MERGE MAIN** |
| 8 | **Đinh Nguyễn Công Bắc** | **Frontend Developer** | `SCRUM-31` | Khởi tạo nhánh `W5-FE` để nâng cấp Web Operations Console React, thay thế mock data bằng API Staging thật & cập nhật GIS Map. | Đang tích hợp Axios / React Query với Backend API Staging (hoàn tất Tuần 06). | **ĐANG THỰC HIỆN** |
| 9 | **Đặng Nguyễn Minh Phi** | **AI & ML Developer** | `SCRUM-32` | Đóng gói Autoencoder & Isolation Forest thành FastAPI microservice (`app/main.py`, `predictor.py`, `classifier.py`) dự đoán dị thường F01–F04. | `app/` (5 modules Python), `requirements-autoencoder.txt`, `tests/test_api.py`, `test_latency.py`. | **ĐÃ MERGE MAIN** |
| 10 | **Nguyễn Đại Phước** | **QA & Test Developer** | `SCRUM-22`<br>`SCRUM-33`<br>*(PR #13)* | Hoàn tất hồ sơ QA Gate G1 (`ATP_GATE_G1_v0.2.md`, `RTM_G1_v0.4.xlsx`, CI verification); bắt đầu thiết lập kịch bản HIL Test & Load Test Gate G2. | `docs/qa/` (9 tài liệu & bảng Excel); 6 file test tự động & `tools/run_ci_tests.py`. | **ĐÃ MERGE PR #13**<br>*(Đang làm `SCRUM-33`)* |

---

## 3. TỔNG KẾT TÍCH HỢP GITHUB & KIỂM TRA CHẤT LƯỢNG MÃ NGUỒN

Tính đến ngày 28/11/2026:
- **Hợp nhất Pull Requests & Nhánh phát triển:** Đã kiểm tra, xử lý xung đột (`requirements-w5.txt`, `security.py`, `.gitignore`, `src/firmware_esp32_idf/`) và merge thành công **4/4 Pull Requests (#12, #13, #14, #15)** cùng **3 nhánh làm việc (`SM-Sprint3`, `Developer-1`, `W5-ML`)** vào nhánh chính `main`.
- **Kiểm thử tự động:** Các bộ kiểm thử đơn vị cốt lõi (giao thức IoT, điều khiển chiếu sáng, MQTT client, payload/topic northbound, safety supervisor, simulator, CI test runner và protocol helper regression) đều chạy ổn định với **141 passed, 6 skipped, 101 subtests passed trong 1.78 giây**.
- **Độ sạch mã nguồn:** Không còn bất kỳ dấu vết xung đột git (0 conflict markers) trên toàn bộ cây thư mục dự án.

---

## 4. KẾ HOẠCH HÀNH ĐỘNG TUẦN TIẾP THEO (TUẦN 06 — HOÀN TẤT SPRINT 3 & GATE G2)

Tuần 06 (từ 02/12/2026 đến 08/12/2026) là tuần nước rút của Sprint 3 nhằm đóng gói sản phẩm và nghiệm thu **Cổng Gate G2 Integrated Pilot**:
- **Đội IoT (`Kiệt & Vượng`):** Chạy thử nghiệm liên hoàn mạch thật ESP32 $\leftrightarrow$ Driver DALI/0-10V $\leftrightarrow$ Mosquitto Staging TLS 8883; chứng minh tính năng Fade mượt, bảo vệ nhiệt 75°C/90°C và Offline Fallback.
- **Đội Web & Backend (`Vỹ, Công, Bắc, Phi`):** Khép kín luồng End-to-End từ Web Operations Console $\rightarrow$ FastAPI Core $\rightarrow$ MQTT $\rightarrow$ ESP32 và luồng Telemetry $\rightarrow$ Ingestion $\rightarrow$ TimescaleDB $\rightarrow$ AI Inference F01–F04.
- **Đội QA & Quản lý (`Phước, Hào, Thanh, Trọng`):** Chạy kịch bản kiểm thử Hardware-in-the-Loop (HIL Test), kiểm thử tải Ingestion (`> 500 msg/s`), đo độ trễ điều khiển (`< 1.5s`), lập hồ sơ nghiệm thu Gate G2 và tổ chức Sprint Review 3 với PCCOM & Thầy Hàn Trung Định.

---

### PHÊ DUYỆT BÁO CÁO TIẾN ĐỘ TUẦN 05

| ĐẠI DIỆN NHÓM SINH VIÊN<br>*(Trưởng nhóm / Product Owner)* | GIẢNG VIÊN HƯỚNG DẪN<br>*(Khoa Công nghệ Thông tin)* | ĐẠI DIỆN DOANH NGHIỆP<br>*(PCCOM CO., LTD)* |
| :---: | :---: | :---: |
| *(Ký và ghi rõ họ tên)*<br><br><br><br>**Trần Đình Trọng** | *(Ký và ghi rõ họ tên)*<br><br><br><br>**Hàn Trung Định** | *(Ký và ghi rõ họ tên)*<br><br><br><br>**Đại diện PCCOM CO., LTD** |
