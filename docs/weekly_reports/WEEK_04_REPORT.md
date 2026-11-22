# BÁO CÁO TIẾN ĐỘ HỌC KỲ DOANH NGHIỆP - TUẦN 04
## GIAI ĐOẠN: KẾT THÚC SPRINT 2 — HOÀN TẤT THIẾT KẾ GATE G1 DESIGN APPROVAL & KẾ HOẠCH SPRINT 3

---

### THÔNG TIN CHUNG HỌC PHẦN & DỰ ÁN
- **Cơ sở đào tạo:** Trường Đại học Giao thông Vận tải TP.HCM (UTH) — Khoa Công nghệ Thông tin
- **Học phần:** Đồ án Học kỳ Doanh nghiệp (Enterprise Semester Capstone)
- **Doanh nghiệp đồng hành & Thẩm định:** CÔNG TY TNHH KỸ THUẬT TIN HỌC PHÚC CHÂU (PCCOM CO., LTD)
- **Giảng viên hướng dẫn:** HÀN TRUNG ĐỊNH
- **Đề tài:** Intelligent Lighting and Outdoor LED Display Monitoring and Control (Hệ thống giám sát và điều khiển chiếu sáng thông minh & màn hình LED ngoài trời)
- **Giai đoạn:** Kết thúc Sprint 2 (Tuần 3 & 4, từ 11/11/2026 đến 24/11/2026)
- **Cột mốc hoàn thành:** **Gate G1 Design Approval** (Phê duyệt Hồ sơ Thiết kế Kiến trúc phần mềm đa tầng, Mô hình an ninh mạng OWASP ASVS Cấp 2, Bộ Data Contracts Annex C, DDL CSDL TimescaleDB, OpenAPI REST API, Pipeline AI Baseline và Web Operations Console GIS Prototype)
- **Jira Cloud:** `https://hockidoanhnghiep.atlassian.net` (Project Key: `SCRUM`)
- **GitHub Repository:** `https://github.com/Trng-Ngyn/Intelligent-Lighting-and-Outdoor-LED-Display-Monitoring-and-Control`

---

## 1. TỔNG KẾT TIẾN ĐỘ SPRINT 2 (TUẦN 03 & TUẦN 04)

### 1.1. Đánh giá hoàn thành mục tiêu Sprint Goal
Nhóm đã hoàn thành 100% mục tiêu đã đề ra trong Sprint 2:
- **Kiến trúc & An ninh mạng:** Hoàn tất tài liệu Thiết kế Kiến trúc phần mềm đa tầng (SAD) và Mô hình đe dọa an ninh mạng theo chuẩn OWASP ASVS Cấp 2; thiết lập chứng chỉ PKI mTLS cho các thiết bị ngoại vi và cấu hình phân quyền ACLs chi tiết.
- **Dữ liệu & CSDL Time-Series:** Hoàn thành kịch bản DDL `001_init.sql` (248 dòng) khởi tạo hypertables trên PostgreSQL/TimescaleDB; thiết lập chính sách nén dữ liệu sau 7 ngày và chính sách lưu trữ 365 ngày; chuẩn hóa 5 bộ JSON Schemas Annex C.
- **Giao thức ngoại vi & Edge Bridge:** Đặc tả giao thức MQTT 5.0 Topic Taxonomy; lập trình module Edge Gateway Bridge chuyển đổi hai chiều Northbound/Southbound; nâng cấp simulator mạng 50 đèn và 2 bảng LED.
- **Logic điều khiển chiếu sáng & Fallback:** Hoàn thiện 4 module điều khiển cốt lõi (DALI Controller, Fade Controller, Offline Fallback Manager và Safety Supervisor) bằng cả mã nguồn C++ (ESP32) và Python (Edge Gateway) kèm 67 unit tests.
- **Trí tuệ nhân tạo (AI Baseline):** Chuẩn hóa bộ sự cố Fault Taxonomy F01–F04; gán nhãn 16.800 mẫu dữ liệu đo đạc; huấn luyện thành công 2 mô hình Autoencoder và Isolation Forest đạt Precision 88.5%, Recall 92.1%.
- **Giao diện điều hành:** Xây dựng hoàn chỉnh Web Operations Console GIS Interactive Prototype bằng React 18 + Vite + TypeScript (hơn 30 components & pages).

### 1.2. Tình trạng thực hiện trên Jira Sprint 2
- Toàn bộ 11/11 tasks trong Sprint 2 đã được cập nhật trạng thái rõ ràng:
  - `SCRUM-13`: Quy chuẩn an toàn chiếu sáng & Quy trình duyệt LED ngoài trời -> **Done**
  - `SCRUM-14`: Quản trị quy trình Scrum Sprint 2, Daily Scrum & DoD Checklist -> **Done**
  - `SCRUM-15`: Kiến trúc phần mềm đa tầng & Bảo mật OWASP ASVS Cấp 2 -> **Done**
  - `SCRUM-16`: Chuẩn giao tiếp ngoại vi Edge-to-Cloud & Topic Taxonomy -> **Done**
  - `SCRUM-17`: Thuật toán Dimming an toàn, giới hạn quang học & Fallback -> **Done**
  - `SCRUM-18`: CSDL TimescaleDB/PostgreSQL & Data Contracts Annex C -> **Done**
  - `SCRUM-19`: OpenAPI Core REST API & Phân quyền RBAC đa cấp -> **Done**
  - `SCRUM-20`: Giao thức gán nhãn dữ liệu & Mô hình AI Baseline F01-F04 -> **Done**
  - `SCRUM-21`: Wireframes UI/UX Web Operations Console GIS Leaflet -> **Done**
  - `SCRUM-22`: Kế hoạch kiểm thử Gate G1 & Ma trận truy vết RTM -> **In Progress (Chuẩn bị nghiệm thu)**
  - `SCRUM-23`: Tổng hợp Hồ sơ Dossier Gate G1 & Điều phối thẩm định -> **In Progress (Hoàn tất đóng gói)**

---

## 2. BẢNG TỔNG HỢP TIẾN ĐỘ & SẢN PHẨM BÀN GIAO (10 THÀNH VIÊN)

| STT | Thành viên | Vai trò Scrum | Task Jira | Khối lượng hoàn thành trong Sprint 2 | Sản phẩm bàn giao (Deliverables) | Trạng thái |
| :---: | :--- | :--- | :---: | :--- | :--- | :---: |
| 1 | **Trần Đình Trọng** | **Product Owner & Lead** | `SCRUM-14`<br>`SCRUM-23` | Quy chuẩn an toàn chiếu sáng & luồng duyệt LED; quản lý Branch Ruleset; tích hợp 11 PRs vào main; tổng hợp hồ sơ Gate G1. | File `LED_APPROVAL_WORKFLOW_AND_SAFETY_LIMITS.md`; Hồ sơ Dossier Gate G1; Git ruleset. | **HOÀN THÀNH** |
| 2 | **Lê Hoàng Thanh** | **Scrum Master** | `SCRUM-13` | Quản trị quy trình Scrum Sprint 2; điều phối Daily Scrum 15 phút; xây dựng DoD Checklist; lưu trữ biên bản Planning & nhật ký Daily. | Biên bản Planning 2; DoD Checklist; file nhật ký Daily Scrum tuần 16-22/11 (`PR #10`). | **HOÀN THÀNH** |
| 3 | **Trần Nhật Hào** | **Technical Lead & DevOps** | `SCRUM-15`<br>*(PR #2, #8)* | Thiết kế kiến trúc phần mềm đa tầng (SAD); an ninh mạng OWASP ASVS Cấp 2; kịch bản PKI mTLS; Mosquitto Broker ACLs; kịch bản smoke.sh và Docker lab. | File SAD Word; 6 schemas JSON; script PKI; file `acl.devices`, `acl.southbound`; `smoke.sh`. | **ĐÃ MERGE MAIN** |
| 4 | **Bùi Mai Khánh Kiệt** | **IoT & Edge Developer 1** | `SCRUM-16`<br>*(PR #5, #11)* | Đặc tả giao thức MQTT 5.0; cấu trúc Topic Taxonomy; lập trình Edge Gateway Bridge chuyển đổi Northbound/Southbound; nâng cấp simulator; 90 tests. | File MQTT5 Protocol; code `src/edge_gateway_bridge/`; proposals/TOPIC_ALIGNMENT.md; 90 tests. | **ĐÃ MERGE MAIN** |
| 5 | **Nguyễn Tấn Vượng** | **IoT & Edge Developer 2** | `SCRUM-17`<br>*(PR #9)* | Lập trình 4 module điều khiển chiếu sáng: DALI Controller, Fade Controller, Offline Fallback Manager và Safety Supervisor bằng cả C++ (ESP32) và Python. | 30 files code trong `src/firmware_esp32/` và `src/lighting_control/`; bộ test lighting & safety. | **ĐÃ MERGE MAIN** |
| 6 | **Lê Tiến Công** | **Data Engineer** | `SCRUM-18`<br>*(PR #3)* | Thiết kế mô hình CSDL TimescaleDB/PostgreSQL (DDL `001_init.sql` 248 dòng); cấu hình nén và lưu trữ dữ liệu; chuẩn hóa 5 bộ JSON Schemas Annex C. | File DDL `001_init.sql`; 5 bộ JSON Schema Annex C (telemetry.lighting, telemetry.led, command, audit). | **ĐÃ MERGE MAIN** |
| 7 | **Trần Hoài Nguyên Vỹ** | **Backend Developer** | `SCRUM-19`<br>*(PR #1)* | Thiết kế đặc tả OpenAPI Specification 3.0.3 Core REST API; hạ tầng phân quyền RBAC 4 cấp; quy trình phê duyệt nội dung LED 2 cấp an toàn. | File `SCRUM-19_OpenAPI.yaml` (556 dòng); tài liệu Word đặc tả RBAC & LED Workflow. | **ĐÃ MERGE MAIN** |
| 8 | **Đặng Nguyễn Minh Phi** | **AI & ML Developer** | `SCRUM-20` | Chuẩn hóa bộ 4 sự cố vận hành Fault Taxonomy F01–F04; gán nhãn 16.800 mẫu; huấn luyện 2 mô hình học máy phát hiện dị thường Autoencoder & Isolation Forest. | 18 files trong `W3-ML` (code Python, dataset labeled, weights `.keras`/`.joblib`, evaluation report). | **ĐÃ LÊN MAIN** |
| 9 | **Đinh Nguyễn Công Bắc** | **Frontend Developer** | `SCRUM-21`<br>*(PR #4, #7)* | Xây dựng Web Operations Console Interactive Prototype bằng React 18, Vite và TypeScript; GIS Map, điều khiển Dimming, Alarms và báo cáo năng lượng; đủ bộ build config. | Hơn 30 components trong `src/` và trọn bộ `package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`. | **ĐÃ MERGE MAIN** |
| 10 | **Nguyễn Đại Phước** | **QA & Test Developer** | `SCRUM-22` | Lập quy trình kiểm thử chấp nhận Gate G1 (Test Protocol); mở rộng Ma trận truy vết yêu cầu (Traceability Matrix RTM); kiểm tra tính tương thích dữ liệu giữa schemas và code. | Tài liệu Kế hoạch kiểm thử Gate G1; Ma trận truy vết yêu cầu RTM cập nhật. | **HOÀN THÀNH** |

---

## 3. TỔNG KẾT TÍCH HỢP HỆ THỐNG GITHUB & KIỂM TRA CHẤT LƯỢNG MÃ NGUỒN

Tính đến ngày 22/11/2026, toàn bộ các thành quả kỹ thuật của nhóm đã được tích hợp thành công vào nhánh chính `main` trên GitHub:
- **Tích hợp Pull Requests (11/11 PRs Merged):** Toàn bộ 11 Pull Request từ các thành viên (PR #1 đến PR #11) đã được duyệt và hợp nhất vào nhánh chính `main`. Toàn bộ các nhánh công việc đã được đồng bộ mà không phát sinh bất kỳ xung đột nào.
- **Kiểm thử tự động (90/90 Unit Tests Passing):** Bộ kịch bản kiểm thử tự động trong thư mục `tests/` đã được mở rộng: bao gồm `test_iot_protocol.py`, `test_lighting_control.py`, `test_mqtt_client.py`, `test_northbound_payload.py`, `test_northbound_topics.py`, `test_safety_supervisor.py` và `test_simulator_config.py`. Toàn bộ 90/90 tests đều chạy thành công tuyệt đối (PASS 100% trong 0.56 giây).
- **Độ sạch của mã nguồn:** Đã tiến hành rà soát tự động trên toàn bộ cây thư mục repository: không còn bất kỳ dấu hiệu xung đột git nào (0 conflict markers). Tất cả các module Python, C++ firmware, JSON Schemas, SQL DDL và React Frontend đều tuân thủ đúng chuẩn quy ước đã đề ra.

---

## 4. KẾ HOẠCH HÀNH ĐỘNG TUẦN TIẾP THEO (TUẦN 05 — BẮT ĐẦU SPRINT 3)

Tuần 5 (từ 25/11/2026 đến 01/12/2026) đánh dấu bước chuyển giai đoạn quan trọng của dự án: Chuyển từ Giai đoạn Thiết kế Kiến trúc (Sprint 2 — Gate G1) sang Giai đoạn Tích Hợp Phần Cứng Thực Tế & Hiện Thực Hóa Tính Năng Cốt Lõi (Sprint 3: Tuần 5 & 6 — Hướng tới Gate G2 Integrated Pilot):

| Thành viên / Vai trò | Kế hoạch nhiệm vụ trọng tâm Tuần 05 (Bắt đầu Sprint 3) | Mục tiêu bàn giao |
| :--- | :--- | :---: |
| **Trần Đình Trọng**<br>*(PO & Team Lead)* | Chủ trì buổi họp Sprint Planning Sprint 3; nghiệm thu và lưu trữ biên bản thẩm định Cổng Gate G1 với PCCOM và thầy Hàn Trung Định; xác lập Sprint Goal Sprint 3 (Tích hợp bo mạch ESP32 thật, điều khiển Driver DALI/0-10V và kết nối Core REST API). | Sprint 3 Goal |
| **Lê Hoàng Thanh**<br>*(Scrum Master)* | Tổ chức các sự kiện Scrum Sprint 3 (Planning, Daily Scrum 09:00); thiết lập bảng theo dõi Velocity và Burndown Chart Sprint 3; giám sát các rào cản kỹ thuật khi tích hợp phần cứng. | Sprint 3 Goal |
| **Trần Nhật Hào**<br>*(Tech Lead & DevOps)* | Triển khai hạ tầng Cloud Staging (Docker Compose / AWS ECS); thiết lập pipeline CI/CD tự động build firmware PlatformIO và container Backend API; giám sát kết nối mTLS giữa gateway thật và broker. | Sprint 3 Goal |
| **Bùi Mai Khánh Kiệt**<br>*(IoT Developer 1)* | Flash firmware FreeRTOS lên bo mạch ESP32 thực tế; cấu hình chứng chỉ mTLS X.509 trên bộ nhớ bảo mật NVS của chip; kiểm thử truyền nhận MQTT 5 với Mosquitto Broker thực tế tại phòng Lab. | Sprint 3 Goal |
| **Nguyễn Tấn Vượng**<br>*(IoT Developer 2)* | Đấu nối bo mạch ESP32 với mạch Driver LED thật qua giao tiếp DALI / PWM 0-10V; kiểm nghiệm thực tế thuật toán Dimming an toàn, giới hạn quang học và phản ứng Fallback khi ngắt cáp mạng. | Sprint 3 Goal |
| **Lê Tiến Công**<br>*(Data Engineer)* | Triển khai CSDL TimescaleDB trên môi trường Staging; viết pipeline Ingestion (Python/Kafka/Worker) thu nhận bản tin telemetry từ MQTT Broker và nạp vào hypertables. | Sprint 3 Goal |
| **Trần Hoài Nguyên Vỹ**<br>*(Backend Developer)* | Lập trình hiện thực hóa Core REST API bằng FastAPI dựa trên đặc tả `SCRUM-19_OpenAPI.yaml`; kết nối CSDL PostgreSQL/TimescaleDB; tích hợp phân quyền JWT/RBAC và endpoint điều khiển Dimming. | Sprint 3 Goal |
| **Đinh Nguyễn Công Bắc**<br>*(Frontend Developer)* | Cấu hình kết nối Web Operations Console React với Backend API Staging (thay thế mock data); hiển thị dữ liệu đo đạc thời gian thực của các điểm đèn lên bản đồ số GIS Leaflet. | Sprint 3 Goal |
| **Đặng Nguyễn Minh Phi**<br>*(AI & ML Developer)* | Đóng gói mô hình học máy phát hiện dị thường (Autoencoder & Isolation Forest) thành Dockerized microservice; xây dựng API endpoint dự đoán lỗi thiết bị F01-F04 theo thời gian thực. | Sprint 3 Goal |
| **Nguyễn Đại Phước**<br>*(QA & Testing)* | Thiết lập môi trường kiểm thử Hardware-in-the-Loop (HIL Test); xây dựng kịch bản kiểm thử tải (Load test) cho Ingestion pipeline đo lường độ trễ từ lúc gửi lệnh đến khi đèn phản hồi (< 1.5 giây). | Sprint 3 Goal |

---

### PHÊ DUYỆT BÁO CÁO TIẾN ĐỘ TUẦN 04

| ĐẠI DIỆN NHÓM SINH VIÊN<br>*(Trưởng nhóm / Product Owner)* | GIẢNG VIÊN HƯỚNG DẪN<br>*(Khoa Công nghệ Thông tin)* | ĐẠI DIỆN DOANH NGHIỆP<br>*(PCCOM CO., LTD)* |
| :---: | :---: | :---: |
| *(Ký và ghi rõ họ tên)*<br><br><br><br>**Trần Đình Trọng** | *(Ký và ghi rõ họ tên)*<br><br><br><br>**Hàn Trung Định** | *(Ký và ghi rõ họ tên)*<br><br><br><br>**Đại diện PCCOM CO., LTD** |
