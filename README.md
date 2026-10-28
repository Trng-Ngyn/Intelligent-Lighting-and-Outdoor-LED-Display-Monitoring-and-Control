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
│   ├── weekly_reports/     # Báo cáo tiến độ hàng tuần nộp LMS (Week 02, Week 03,...)
│   └── architecture/       # Thiết kế kiến trúc, Data contracts, Security threat models
├── src/
│   ├── edge/               # Mã nguồn Edge Gateway / Device Controller (DALI, D4i, MQTT)
│   ├── backend/            # API Core & Content Distribution Engine
│   ├── frontend/           # Web Console & GIS Dashboard
│   └── ml_service/         # Mô hình Adaptive Lighting & Anomaly Detection
├── tests/                  # Bộ kiểm thử tự động (AT 01 - AT 12)
└── tools/                  # Script tự động hóa đồng bộ Jira, tạo repo GitHub
```

