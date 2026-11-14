# Intelligent Lighting and Outdoor LED Display Monitoring and Control

> **AI and ML-enabled IoT & Cloud Platform for Outdoor Lighting & LED Display Operations**  
> **Enterprise Partner:** PCCOM CO., LTD (PHÚC CHÂU COMPUTER - TECHNICAL LIMITED COMPANY)  
> **Framework:** Agile Scrum (16-week delivery, 8 Sprints)

---

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
│   ├── edge_simulator/     # Virtual Edge Simulator MQTT 5 (đèn/LED/gateway)
│   ├── backend/            # Mock Cloud Service & Core API
│   ├── firmware_esp32/     # Firmware gateway/controller ESP32
│   └── frontend/           # Web Console & GIS Dashboard
├── tests/                  # Unit test giao thức và cấu hình simulator
└── tools/                  # Probe MQTT 5, script Jira, tạo repo GitHub
```

## 🔌 MQTT 5 Protocol & Simulator
- Đặc tả giao thức: [`docs/specifications/MQTT5_COMMUNICATION_PROTOCOL.md`](docs/specifications/MQTT5_COMMUNICATION_PROTOCOL.md)
- Hướng dẫn simulator: [`src/edge_simulator/README.md`](src/edge_simulator/README.md)
- Báo cáo E2E/LWT: [`docs/test_reports/MQTT5_E2E_REPORT.md`](docs/test_reports/MQTT5_E2E_REPORT.md)
- Changelog: [`docs/CHANGELOG.md`](docs/CHANGELOG.md)

Chạy nhanh với broker công cộng:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item config.example.json config.json
.\.venv\Scripts\python.exe src\edge_simulator\virtual_lighting_network.py --max-devices 5
```

