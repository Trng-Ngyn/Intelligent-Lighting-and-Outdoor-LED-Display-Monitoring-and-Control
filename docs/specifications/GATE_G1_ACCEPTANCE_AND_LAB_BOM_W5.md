# HỒ SƠ NGHIỆM THU GATE G1, DANH MỤC THIẾT BỊ LAB & QUẢN TRỊ BACKLOG SPRINT 3 (W5-PO)

**Dự án:** Intelligent Lighting and Outdoor LED Display Monitoring and Control  
**Mã công việc Jira:** `SCRUM-24` (Sprint 3 — Tuần 5)  
**Người thực hiện:** Trần Đình Trọng (Product Owner & Team Lead)  
**Giảng viên hướng dẫn:** HÀN TRUNG ĐỊNH (Khoa CNTT — Trường ĐH Giao thông Vận tải TP.HCM)  
**Doanh nghiệp thẩm định:** CÔNG TY TNHH KỸ THUẬT TIN HỌC PHÚC CHÂU (PCCOM CO., LTD)  
**Ngày cập nhật:** 28/11/2026

---

## 1. XÁC NHẬN NGHIỆM THU CỔNG GATE G1 (DESIGN APPROVAL)

Toàn bộ 8/8 hạng mục cốt lõi của **Gate G1 Design Approval** đã được hoàn thiện, kiểm chứng tự động trên CI/CD (`SCRUM-22`, PR #13) và thông qua thẩm định:

| STT | Tiêu chí Gate G1 | Tài liệu / Mã nguồn đối chứng | Mã Jira | Trạng thái |
| :---: | :--- | :--- | :---: | :---: |
| 1 | Kiến trúc phần mềm đa tầng (SAD) & Threat Model OWASP ASVS L2 | `docs/specifications/` & `deploy/staging/` (`PR #2, #8`) | `SCRUM-15` | **ĐẠT** |
| 2 | Quy chuẩn an toàn chiếu sáng & Luồng duyệt nội dung LED đa tầng | `docs/LED_APPROVAL_WORKFLOW_AND_SAFETY_LIMITS.md` | `SCRUM-13` | **ĐẠT** |
| 3 | Giao thức truyền thông MQTT 5.0 Topic Taxonomy & Edge Bridge | `docs/MQTT5_COMMUNICATION_PROTOCOL.md`, `src/edge_gateway_bridge/` | `SCRUM-16` | **ĐẠT** |
| 4 | Thuật toán Dimming đường cong DALI, Fade & Thermal Derating | `src/firmware_esp32/`, `src/lighting_control/` (`PR #9`) | `SCRUM-17` | **ĐẠT** |
| 5 | Mô hình CSDL TimescaleDB & Bộ Data Contracts Annex C | `database/migrations/001_init.sql`, `docs/data_contracts/` (`PR #3`) | `SCRUM-18` | **ĐẠT** |
| 6 | Đặc tả OpenAPI 3.0.3 Core REST API & Phân quyền RBAC 4 cấp | `docs/backend/SCRUM-19/CoreAPIOpenAPI_3.0.3.yaml` (`PR #1`) | `SCRUM-19` | **ĐẠT** |
| 7 | Giao thức gán nhãn & Mô hình AI Baseline phát hiện lỗi F01–F04 | `docs/ai/`, weights `.keras`/`.joblib` (`16.800` mẫu) | `SCRUM-20` | **ĐẠT** |
| 8 | Giao thức kiểm thử chấp nhận ATP G1, Ma trận RTM v0.4 & CI Tests | `docs/qa/ATP_GATE_G1_v0.2.md`, `docs/qa/RTM_G1_v0.4.xlsx` (`PR #13`) | `SCRUM-22` | **ĐẠT** |

---

## 2. DANH MỤC THIẾT BỊ PHẦN CỨNG PHÒNG LAB (HARDWARE BOM — GATE G2 PILOT)

Phục vụ tích hợp Hardware-in-the-Loop (HIL) trong Sprint 3 (Tuần 5 & Tuần 6):

| STT | Tên thiết bị / Linh kiện | Thông số kỹ thuật chính | Số lượng | Phụ trách tích hợp |
| :---: | :--- | :--- | :---: | :--- |
| 1 | Bo mạch vi điều khiển **ESP32-WROOM-32 DevKit** | Dual-core 240MHz, Wi-Fi, NVS Flash 4MB, hỗ trợ mTLS X.509 & ESP-IDF 5.4 | 02 bộ | Bùi Mai Khánh Kiệt (`SCRUM-27`) |
| 2 | Module giao tiếp **DALI Master / Opto-Isolated** | Chuẩn IEC 62386, cách ly quang 2.5kV, nguồn bus DALI 16V | 01 bộ | Nguyễn Tấn Vượng (`SCRUM-28`) |
| 3 | Mạch chuyển đổi **PWM-to-0-10V Analog Dimmer** | Tín hiệu điều khiển GPIO PWM 5V sang chuẩn 0-10V công nghiệp | 02 mạch | Nguyễn Tấn Vượng (`SCRUM-28`) |
| 4 | Bộ nguồn **LED Driver DALI / 0-10V** & Đèn LED tải mẫu | Công suất 30W–50W, hỗ trợ dimming 0–100% | 02 bộ | Nguyễn Tấn Vượng (`SCRUM-28`) |
| 5 | Cảm biến quang học **BH1750** (I2C) & Cảm biến nhiệt **NTC / DS18B20** | Đo độ rọi (Lux) và giám sát nhiệt độ ngưỡng 75°C / 90°C | 02 bộ | Kiệt & Vượng |
| 6 | Module chuyển đổi **RS485 / Modbus RTU** & Đồng hồ đo điện năng | Đọc thông số V, A, W, Wh, PF thời gian thực | 01 bộ | Kiệt & Công (`SCRUM-29`) |

---

## 3. QUẢN TRỊ BACKLOG SPRINT 3 & TIÊU CHÍ CHẤP NHẬN GATE G2 (INTEGRATED PILOT)

- **Sprint Goal Sprint 3:** *"Tích hợp phần cứng ESP32 với Driver LED DALI/0-10V (HIL), thông luồng Telemetry MQTT 5 lên Cloud Staging, Core REST API & Ingestion TimescaleDB đạt mốc Gate G2."*
- **Các chỉ tiêu kỹ thuật (SLA) bắt buộc cho nghiệm thu Gate G2 vào cuối Tuần 6:**
  - **Độ trễ điều khiển End-to-End** (Web Console $\rightarrow$ FastAPI $\rightarrow$ MQTT 5 $\rightarrow$ ESP32 $\rightarrow$ LED Driver): `< 1.5 giây`.
  - **Độ trễ suy luận AI Anomaly (F01–F04):** `< 150 ms` trên mỗi batch 50 mẫu.
  - **Tải Ingestion Pipeline (TimescaleDB):** Xử lý ổn định `> 500 bản tin/giây`, tỷ lệ mất gói `< 0.1%`.
  - **An toàn & Dự phòng:** Ngắt/giảm tải quá nhiệt trong `< 3.0 giây`; kích hoạt Offline Fallback tự động khi mất kết nối mạng quá `5 phút`.
