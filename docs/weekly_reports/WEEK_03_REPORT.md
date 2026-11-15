# BÁO CÁO TIẾN ĐỘ HỌC KỲ DOANH NGHIỆP - TUẦN 03
## GIAI ĐOẠN: SPRINT 2 — THIẾT KẾ KIẾN TRÚC CHI TIẾT & CHUẨN BỊ GATE G1 APPROVAL

---

### THÔNG TIN CHUNG HỌC PHẦN & DỰ ÁN
- **Cơ sở đào tạo:** Trường Đại học Giao thông Vận tải TP.HCM (UTH) — Khoa Công nghệ Thông tin
- **Học phần:** Đồ án Học kỳ Doanh nghiệp (Enterprise Semester Capstone)
- **Doanh nghiệp đồng hành & Thẩm định:** CÔNG TY TNHH KỸ THUẬT TIN HỌC PHÚC CHÂU (PCCOM CO., LTD)
- **Giảng viên hướng dẫn:** ThS. Võ Tấn Sang
- **Đề tài:** Intelligent Lighting and Outdoor LED Display Monitoring and Control (Hệ thống giám sát và điều khiển chiếu sáng thông minh & màn hình LED ngoài trời)
- **Mô hình triển khai:** Agile Scrum Framework (Sprint 2: Tuần 3 & 4, từ 11/11/2026 đến 24/11/2026)
- **Cột mốc thẩm định hướng tới:** **Gate G1 Design Approval** (Phê duyệt hồ sơ thiết kế kiến trúc phần mềm, mô hình an ninh mạng, chuẩn hợp đồng dữ liệu, giao thức điều khiển và pipeline AI)
- **Jira Cloud:** `https://hockidoanhnghiep.atlassian.net` (Project Key: `SCRUM`)
- **GitHub Repository:** `https://github.com/Trng-Ngyn/Intelligent-Lighting-and-Outdoor-LED-Display-Monitoring-and-Control`

---

## 1. MỤC TIÊU SPRINT 2 & QUẢN TRỊ QUY TRÌNH SCRUM

### 1.1. Mục tiêu trọng tâm của Sprint 2 (Sprint Goal)
> *"Hoàn thiện toàn diện Hồ sơ thiết kế kiến trúc phần mềm đa tầng (SAD), Mô hình đe dọa an ninh mạng theo chuẩn OWASP ASVS Cấp 2, Bộ Data Contracts & Schema TimescaleDB, Giao thức gán nhãn AI Baseline phát hiện bất thường F01–F04, Đặc tả OpenAPI Core REST API và bộ Wireframes Web Console GIS hướng tới thẩm định Cổng Gate G1 Design Approval với Doanh nghiệp PCCOM."*

### 1.2. Kỷ luật vận hành quy trình Scrum
- **Họp Daily Scrum 15 phút:** Được duy trì đều đặn vào lúc 09:00 sáng mỗi ngày. Từng thành viên trả lời nhanh 3 câu hỏi cốt lõi: (1) Hôm qua đã làm gì để đạt Sprint Goal? (2) Hôm nay sẽ làm gì? (3) Có khó khăn, trở ngại (impediments) nào cản trở không?
- **Tiến độ Sprint Backlog:** Kết thúc Tuần 3, toàn bộ 6 module kỹ thuật nền tảng đều hoàn thành 100% các bản đặc tả, schema và prototypes thực nghiệm.
- **Thiết lập Branch Ruleset bảo vệ nhánh main:** Đã kích hoạt cơ chế bảo vệ nhánh chính trên GitHub, bắt buộc tối thiểu 1 Approving Review trước khi merge, cấm Force Push và cấm xóa nhánh.

---

## 2. BẢNG TỔNG HỢP TIẾN ĐỘ & PHÂN CÔNG NHIỆM VỤ (10 THÀNH VIÊN)

| STT | Thành viên | Vai trò Scrum | Task Jira | Khối lượng thực hiện Tuần 3 | Sản phẩm bàn giao (Deliverables) | Trạng thái |
| :---: | :--- | :--- | :---: | :--- | :--- | :---: |
| 1 | **Trần Đình Trọng** | **Product Owner & Team Lead** | `SCRUM-14`<br>`SCRUM-23` | Tổng hợp quy chuẩn an toàn chiếu sáng & quy trình phê duyệt LED ngoài trời; thiết lập Branch Ruleset bảo vệ nhánh main; tích hợp 4 PRs vào main; chuẩn bị hồ sơ G1. | File đặc tả `LED_APPROVAL_WORKFLOW_AND_SAFETY_LIMITS.md`; cấu hình Ruleset GitHub; hồ sơ nghiệm thu G1. | **HOÀN THÀNH** |
| 2 | **Lê Hoàng Thanh** | **Scrum Master** | `SCRUM-13` | Quản trị quy trình Scrum Sprint 2; điều phối Daily Scrum 15 phút; theo dõi tiến độ trên Jira Board; lập bảng kiểm Definition of Done cho Gate G1. | Biên bản Daily Scrum; báo cáo tiến độ Sprint 2; DoD Checklist Gate G1. | **HOÀN THÀNH** |
| 3 | **Trần Nhật Hào** | **Technical Lead & DevOps** | `SCRUM-15`<br>*(PR #2)* | Thiết kế kiến trúc phần mềm đa tầng; lập mô hình đe dọa an ninh mạng OWASP ASVS Cấp 2; script tạo chứng chỉ PKI mTLS; config Mosquitto ACL; kịch bản smoke test AWS ECS. | File `SAD_Technical_Architecture.docx`; 6 JSON contract schemas; script `generate-pki.sh`; `mosquitto.conf`; `smoke.sh`. | **ĐÃ MERGE MAIN** |
| 4 | **Bùi Mai Khánh Kiệt** | **IoT & Edge Developer 1** | `SCRUM-16`<br>*(PR #5)* | Đặc tả giao thức ngoại vi Edge-to-Cloud MQTT 5.0; cấu trúc Topic Taxonomy; cơ chế User Properties; kiểm thử thông điệp LWT/Heartbeat; nâng cấp simulator. | File `MQTT5_COMMUNICATION_PROTOCOL.md`; code `src/iot_protocol/`; test suite `test_iot_protocol.py`. | **HOÀN THÀNH** |
| 5 | **Nguyễn Tấn Vượng** | **IoT & Edge Developer 2** | `SCRUM-17` | Nghiên cứu cơ chế Fallback cục bộ khi mất kết nối mạng (Local Fallback State Machine); thuật toán Dimming tự hành thích ứng môi trường; mạch bảo vệ quá dòng Driver. | Bản thiết kế thuật toán Fallback an toàn; sơ đồ mạch bảo vệ Driver 3.3V/5V/12V. | **HOÀN THÀNH** |
| 6 | **Lê Tiến Công** | **Data Engineer** | `SCRUM-18`<br>*(PR #3)* | Thiết kế mô hình CSDL quan hệ kết hợp Time-Series (PostgreSQL + TimescaleDB); tối ưu Hypertables; chuẩn hóa 5 bộ Data Contracts JSON Schemas Annex C. | File DDL `001_init.sql` (248 dòng SQL); 5 bộ JSON Schema chuẩn Annex C (telemetry, command, audit). | **ĐÃ MERGE MAIN** |
| 7 | **Trần Hoài Nguyên Vỹ** | **Backend Developer** | `SCRUM-19`<br>*(PR #1)* | Thiết kế đặc tả OpenAPI Specification 3.0.3 Core REST API; hạ tầng phân quyền RBAC đa cấp (4 roles); tài liệu quy trình phê duyệt nội dung LED số đa tầng. | File `SCRUM-19_OpenAPI.yaml` (556 dòng); tài liệu Word `SCRUM-19_Thiet_ke_API_RBAC_LED_Workflow.docx`. | **ĐÃ MERGE MAIN** |
| 8 | **Đặng Nguyễn Minh Phi** | **AI & ML Developer** | `SCRUM-20` | Xây dựng quy chuẩn phân loại sự cố Fault Taxonomy F01–F04; giao thức gán nhãn Ground Truth 16.800 mẫu; thiết kế và huấn luyện mô hình học máy AI Baseline (Autoencoder & Isolation Forest). | 18 files trong `W3-ML` (code Python, dataset `pilot_50_led_labeled.csv`, weights `.keras`/`.joblib`, báo cáo đánh giá). | **ĐÃ LÊN MAIN** |
| 9 | **Đinh Nguyễn Công Bắc** | **Frontend Developer** | `SCRUM-21`<br>*(PR #4)* | Xây dựng Web Operations Console Interactive Prototype bằng React + Vite + TypeScript; tích hợp bản đồ số GIS Leaflet, điều khiển Dimming, quản lý màn hình LED, báo cáo năng lượng. | Bộ source code hoàn chỉnh trong `src/` (hơn 30 components & pages: GISMap, Dashboard, Dimming, Alarms...). | **ĐÃ MERGE MAIN** |
| 10 | **Nguyễn Đại Phước** | **QA & Test Developer** | `SCRUM-22` | Lập kế hoạch kiểm thử chấp thuận Gate G1; đối chiếu ma trận truy vết yêu cầu (Traceability Matrix) từ RFP đến các tài liệu thiết kế kiến trúc và schemas; thẩm định độ phủ kiểm thử. | Tài liệu Kế hoạch kiểm thử Gate G1; Ma trận truy vết yêu cầu (Requirements Traceability Matrix - RTM). | **HOÀN THÀNH** |

---

## 3. CHI TIẾT CÁC THÀNH QUẢ KỸ THUẬT NỔI BẬT ĐẠT ĐƯỢC

### 3.1. Kiến trúc phần mềm đa tầng & Bảo mật an ninh mạng (SCRUM-15)
- Technical Lead Trần Nhật Hào đã hoàn thành tài liệu Thiết kế Kiến trúc Phần mềm (Software Architecture Document - SAD) định dạng Word theo chuẩn IEEE/ISO.
- Hệ thống được tổ chức thành 4 phân tầng độc lập:
  - Tầng 1 (Edge Layer): Thiết bị Gateway/Controller biên kết nối đèn DALI/D4i và màn hình LED ngoài trời.
  - Tầng 2 (Ingestion Layer): Mosquitto MQTT Broker bảo mật mTLS 2 chiều kèm ACL chi tiết cho từng device.
  - Tầng 3 (Service & Processing Layer): Core REST API, Workflow Engine, TimescaleDB và AI Anomaly Detection Pipeline.
  - Tầng 4 (Presentation Layer): Web Operations Console tích hợp bản đồ số GIS phục vụ trung tâm điều hành.
- Đáp ứng chuẩn bảo mật OWASP ASVS Cấp 2: Tự động hóa tạo và quản lý chứng chỉ PKI X.509 (`generate-pki.sh`), mã hóa dữ liệu đường truyền và cấu hình hạ tầng containerized trên AWS ECS theo nguyên tắc đặc quyền tối thiểu (Least Privilege).

### 3.2. Chuẩn hóa Data Contracts Annex C & CSDL TimescaleDB (SCRUM-18)
- Data Engineer Lê Tiến Công đã hoàn thiện kịch bản DDL `001_init.sql` (248 dòng lệnh SQL) khởi tạo cơ sở dữ liệu trên PostgreSQL kết hợp TimescaleDB:
  - Bảng quan hệ cấu hình: `devices`, `zones`, `led_panels`, `schedules`, `users`.
  - Hypertables chuỗi thời gian: `lighting_telemetry`, `led_telemetry`, `audit_events`.
  - Chính sách nén dữ liệu (Compression Policy): Tự động nén dữ liệu cũ sau 7 ngày, giúp giảm hơn 80% dung lượng lưu trữ đĩa cứng.
  - Chính sách lưu trữ dữ liệu (Retention Policy): Duy trì dữ liệu trong vòng 365 ngày để phục vụ phân tích xu hướng.
- Chuẩn hóa 5 bộ JSON Schemas theo đúng định dạng phụ lục Annex C của hồ sơ đề tài PCCOM.

### 3.3. Đặc tả Core REST API OpenAPI 3.0.3 & Phân quyền RBAC (SCRUM-19)
- Backend Developer Trần Hoài Nguyên Vỹ đã thiết kế file `SCRUM-19_OpenAPI.yaml` gồm 556 dòng theo chuẩn OAS 3.0.3 quốc tế.
- Đặc tả toàn diện các endpoint:
  - Xác thực & Phân quyền: Đăng nhập JWT, quản lý phiên làm việc, phân quyền 4 cấp (Admin, Operator, Content Manager, Auditor).
  - Quản trị thiết bị: Tra cứu trạng thái 50 đèn và 2 màn hình LED, tra cứu lịch sử đo đạc telemetry.
  - Điều khiển chiếu sáng: Dimming tức thời, lập lịch chiếu sáng theo vùng (zone schedules).
  - Phê duyệt nội dung số màn hình LED: Luồng kiểm duyệt 2 cấp (Draft -> Review -> Approved -> Published) đảm bảo an toàn tuyệt đối khi phát nội dung nơi công cộng.

### 3.4. Nghiên cứu & Huấn luyện Pipeline AI Baseline phát hiện bất thường (SCRUM-20)
- AI/ML Developer Đặng Nguyễn Minh Phi đã chuẩn hóa bộ 4 sự cố vận hành cốt lõi (Fault Taxonomy F01–F04):
  - F01: Quá nhiệt Driver / Đèn LED (> 80°C).
  - F02: Bất thường tiêu thụ điện năng / Rò rỉ dòng điện (Power drift / Current surge).
  - F03: Suy hao quang thông bóng đèn theo thời gian (Lumen degradation).
  - F04: Mất đồng bộ hiển thị màn hình LED (Display sync dropout).
- Xây dựng giao thức gán nhãn Ground Truth và huấn luyện thành công 2 mô hình học máy phát hiện dị thường không giám sát: Autoencoder Neural Network và Isolation Forest.
- Kết quả kiểm thử thực nghiệm trên 16.800 mẫu dữ liệu đo đạc:
  - Độ chính xác Precision: Đạt 88.5% (Vượt yêu cầu đề tài $\ge 85\%$).
  - Độ nhạy Recall: Đạt 92.1% (Vượt yêu cầu đề tài $\ge 90\%$).
  - Tỷ lệ cảnh báo sai False Positive Rate: < 5%.

### 3.5. Web Operations Console Interactive Prototype (SCRUM-21)
- Frontend Developer Đinh Nguyễn Công Bắc đã phát triển hoàn chỉnh bộ giao diện bảng điều khiển trung tâm bằng React 18, Vite và TypeScript.
- Bộ ứng dụng gồm hơn 30 component và màn hình chức năng:
  - Bản đồ số GIS tương tác: Định vị trực quan 50 cột đèn và 2 màn hình LED ngoài trời, hiển thị trạng thái bằng mã màu (Xanh: bình thường, Vàng: cảnh báo, Đỏ: sự cố).
  - Điều khiển Dimming: Thanh trượt điều chỉnh cường độ sáng tức thời từng đèn hoặc theo nhóm.
  - Phân tích năng lượng: Biểu đồ trực quan hóa điện năng tiêu thụ theo thời gian thực (PowerChart).
  - Quản lý màn hình LED & Trung tâm báo động (Alarms).

### 3.6. Giao thức ngoại vi Edge-to-Cloud MQTT 5.0 (SCRUM-16)
- IoT Developer Bùi Mai Khánh Kiệt đã chuẩn hóa tài liệu giao thức `MQTT5_COMMUNICATION_PROTOCOL.md` và mã nguồn trong `src/iot_protocol/`.
- Định nghĩa phân cấp Topic Taxonomy rõ ràng (`telemetry`, `command`, `status`, `alert`), tích hợp User Properties để truyền Correlation ID và chữ ký bảo mật HMAC, cấu hình thông điệp LWT tự động cảnh báo khi mất kết nối.

---

## 4. TỔNG KẾT TÍCH HỢP HỆ THỐNG GITHUB & BRANCH RULESET

Vào ngày 15/11/2026, toàn bộ các thành quả kỹ thuật của nhóm đã được tích hợp thành công vào nhánh `main` trên GitHub:
- **Hợp nhất mã nguồn (PR Merging):** Đã merge thành công 4 Pull Request lớn (PR #1 Backend, PR #2 Architecture, PR #3 Database, PR #4 Frontend) mà không phát sinh bất kỳ xung đột nào (0 merge conflicts), bổ sung hơn 76.000 dòng mã nguồn và tài liệu.
- **Kích hoạt Branch Ruleset bảo vệ nhánh main:** Đã thiết lập luật bảo vệ trên GitHub: bắt buộc có ít nhất 1 Approving Review trước khi merge, cấm Force Push và cấm xóa nhánh. Quy định này đảm bảo 100% mã nguồn từ Tuần 4 phải tuân thủ nghiêm ngặt quy trình review của nhóm.
- **Mức độ sẵn sàng:** Mã nguồn hiện tại đồng bộ đầy đủ cả 4 tầng kiến trúc (Edge Simulator, Core API Specs, TimescaleDB DDL, AI Baseline Models & Frontend React Console), sẵn sàng 100% cho buổi thẩm định Gate G1.

---

## 5. KẾ HOẠCH HÀNH ĐỘNG TUẦN 04 (GATE G1 DESIGN APPROVAL)

1. **Đóng gói Hồ sơ Nghiệm thu Cổng Gate G1:** Tổng hợp trọn bộ tài liệu kỹ thuật (SAD, OpenAPI YAML, TimescaleDB SQL, AI Report, Prototype Video/Demo) thành Dossier thẩm định hoàn chỉnh nộp Doanh nghiệp PCCOM và Giảng viên hướng dẫn.
2. **Họp Sprint Review & Sprint Retrospective:** Đánh giá hiệu suất nhóm qua Sprint Burndown Chart, rút kinh nghiệm chuẩn bị cho Sprint 3 (Phát triển tính năng và tích hợp thiết bị phần cứng thực ESP32).
3. **Tổ chức Thẩm định & Ký Biên bản Nghiệm thu Gate G1:** Báo cáo bảo vệ thiết kế kiến trúc hệ thống trước Doanh nghiệp và Nhà trường UTH để chính thức thông qua Cổng Gate G1.

---

### PHÊ DUYỆT BÁO CÁO TIẾN ĐỘ TUẦN 03

| ĐẠI DIỆN NHÓM SINH VIÊN<br>*(Trưởng nhóm / Product Owner)* | GIẢNG VIÊN HƯỚNG DẪN<br>*(Khoa Công nghệ Thông tin)* | ĐẠI DIỆN DOANH NGHIỆP<br>*(PCCOM CO., LTD)* |
| :---: | :---: | :---: |
| *(Ký và ghi rõ họ tên)*<br><br><br><br>**Trần Đình Trọng** | *(Ký và ghi rõ họ tên)*<br><br><br><br>**ThS. Võ Tấn Sang** | *(Ký và ghi rõ họ tên)*<br><br><br><br>**Đại diện PCCOM CO., LTD** |
