# BÁO CÁO TIẾN ĐỘ HÀNG TUẦN - TUẦN 02 (WEEKLY REPORT 02)
**Học phần:** Đồ án Học kỳ Doanh nghiệp  
**Dự án:** Intelligent Lighting and Outdoor LED Display Monitoring and Control  
**Doanh nghiệp tiếp nhận:** CÔNG TY TNHH KỸ THUẬT TIN HỌC PHÚC CHÂU (PCCOM CO., LTD)  
**Mô hình áp dụng:** Agile Scrum (Sprint 1: Weeks 1 - 2 | Cổng nghiệm thu: Gate G0 Readiness)  
**Chiến lược kỹ thuật:** **Software-First & Virtual Edge Simulation** (Ưu tiên hoàn thiện phần mềm Cloud, Web Console và Core API với bộ mô phỏng 50 điểm đèn trước khi triển khai phần cứng ESP32 ở các sprint sau)  
**Jira Workspace:** https://hockidoanhnghiep.atlassian.net (Project Key: SCRUM)  
**GitHub Repository:** https://github.com/Trng-Ngyn/Intelligent-Lighting-and-Outdoor-LED-Display-Monitoring-and-Control  
**Hạn chót nộp LMS:** Thứ Tư, 11/11/2026, 12:00 AM  

---

## 1. Cơ cấu Nhóm Scrum & Phân chia 10 Vai trò (RFP Section 11)

| STT | Họ tên / Tài khoản | Vai trò trong nhóm Scrum | Nhiệm vụ chính trong dự án | Mã Task phụ trách |
| :---: | :--- | :--- | :--- | :---: |
| 1 | **Trần Đình Trọng** | **Product Owner (PO) & Team Leader** | **Vai trò cao nhất:** Định nghĩa Product Goal; phân loại và ưu tiên Product Backlog; đại diện làm việc và nghiệm thu với PCCOM CO., LTD; ký nghiệm thu các mốc G0 - G4. | `SCRUM-1`<br/>`SCRUM-12` |
| 2 | **Thanh Lê** | **Scrum Master (SM)** | Tổ chức các sự kiện Scrum (Daily Scrum 09:00 hàng ngày, Sprint Planning, Review & Retro); xây dựng DoD checklist và theo dõi tiến độ trên Jira. | `SCRUM-7` |
| 3 | **Nhat Hao Tran** | **Technical Lead & DevOps** | Thiết kế kiến trúc tổng thể phần mềm; cấu hình CI/CD GitHub Actions, áp dụng chuẩn bảo mật OWASP ASVS và phân quyền hệ thống. | `SCRUM-5` |
| 4 | **Kiệt** | **IoT & Edge Developer 1** | Xây dựng bộ mô phỏng thiết bị ngoại vi (Virtual IoT Edge Simulator), cấu hình định tuyến bản tin MQTT 5 (End-to-End Telemetry Slice). | `SCRUM-6` |
| 5 | **Lê Tiến Công** | **Data Engineering Developer** | Thiết kế luồng thu thập dữ liệu đo đạc (telemetry: W, Wh, lux, nhiệt độ); xây dựng Data Schema chuẩn Annex C và cơ chế xác thực dữ liệu. | `SCRUM-8` |
| 6 | **Tấn Vượng** | **IoT & Edge Developer 2** | Lập trình logic điều khiển Driver ảo, thuật toán Dimming an toàn, cơ chế Fallback cục bộ khi mất mạng và bảo vệ quá nhiệt phần mềm. | `SCRUM-3` |
| 7 | **Trần Nguyên Vỹ**| **Backend Developer** | Xây dựng Core API service, dịch vụ quản lý trạng thái thiết bị, phân quyền RBAC/MFA, quy trình phê duyệt phát hành nội dung LED đa tầng (DSP 02-04). | `SCRUM-4` |
| 8 | **Minh Phi** | **ML Developer** | Phân loại taxonomy sự cố thiết bị (F01 - F04), nghiên cứu mô hình phát hiện bất thường thiết bị/hệ thống mạng (AI 02, chuẩn AT 06). | `SCRUM-9` |
| 9 | **Bắc Công** | **Frontend Developer** | Phát triển Giao diện điều hành trung tâm (Web Operations Console), bản đồ số GIS Leaflet hiển thị trực quan 50 điểm đèn và 2 màn hình LED. | `SCRUM-10` |
| 10 | **Phuoc Nguyen** | **QA Engineering Developer** | Xây dựng kịch bản kiểm thử tự động cho các tiêu chí nghiệm thu Gate G0 (AT 01 - AT 05); quản lý ma trận truy vết yêu cầu (RTM). | `SCRUM-11` |

---

## 2. Mục tiêu Sprint 1 (Sprint Goal - Gate G0 Readiness)
> **Sprint Goal:** Thiết lập toàn diện hạ tầng phát triển phần mềm (Jira Scrum, GitHub Repository, CI/CD); hoàn thiện khảo sát phạm vi Pilot (2 địa điểm, 50 điểm chiếu sáng, 2 màn hình LED ngoài trời); xây dựng bộ mô phỏng Virtual Edge Node và giao diện Web Console điều hành trung tâm; vượt qua cổng kiểm tra tính khả thi kỹ thuật **Gate G0 Readiness**.

---

## 3. Bảng Phân Công Công Việc, Nhật Ký Git Commits & 73 Giờ Log Work

Nhóm đã hoàn thành xuất sắc toàn bộ các hạng mục công việc với 11 commits trên GitHub tương ứng với 73 giờ logwork trên Jira:

| Mã Task Jira | Thành viên | Vai trò | Tóm tắt công việc đã thực hiện | Ngày commit / log | Giờ đã log | Trạng thái Jira |
| :---: | :--- | :---: | :--- | :---: | :---: | :---: |
| **SCRUM-1** | Trần Đình Trọng | PO | Khảo sát 2 site, 50 điểm đèn, 2 màn hình LED; xác định phạm vi 4 Package và khởi tạo Backlog. | 28/10/2026 | 8h | **Done** |
| **SCRUM-7** | Thanh Lê | SM | Thiết lập quy chuẩn DoD checklist, kế hoạch họp Scrum và điều phối công việc Sprint 1. | 28/10/2026 | 4h | **Done** |
| **SCRUM-5** | Nhat Hao Tran | TL | Khởi tạo CI/CD pipeline GitHub Actions, chuẩn bảo mật OWASP ASVS mức 2 và cấu hình Jira. | 30/10/2026 | 8h | **Done** |
| **SCRUM-6** | Kiệt | IoT | Xây dựng Virtual IoT Edge Simulator, kiểm tra luồng phát telemetry mẫu 1 KiB/phút qua MQTT 5. | 31/10/2026 | 8h | **Done** |
| **SCRUM-8** | Lê Tiến Công | DE | Hoàn thành Data Schema (W, Wh, V, A, lux, °C) theo Annex C và kiểm tra JSON Schema validation. | 05/11/2026 | 7h | **Done** |
| **SCRUM-3** | Tấn Vượng | IoT | Lập trình logic điều khiển Dimming an toàn và thuật toán Fallback tự động khi mất kết nối Cloud. | 06/11/2026 | 6h | **Done** |
| **SCRUM-4** | Trần Nguyên Vỹ | BE | Xây dựng dịch vụ Core API, lưu đệm danh sách phát màn hình LED (Cache fallback) khi ngắt WAN. | 06/11/2026 | 5h | **Done** |
| **SCRUM-9** | Minh Phi | ML | Xây dựng bảng phân loại lỗi (Fault Taxonomy F01 - F04) và chuẩn bị tập dữ liệu kiểm thử AT 06. | 07/11/2026 | 8h | **Done** |
| **SCRUM-10**| Bắc Công | FE | Phát triển Web Operations Console tích hợp bản đồ GIS Leaflet hiển thị trực quan 50 cột đèn. | 07/11/2026 | 6h | **Done** |
| **SCRUM-11**| Phuoc Nguyen | QA | Xây dựng ma trận truy vết RTM và bộ kịch bản kiểm thử tự động bench test cho Gate G0. | 09/11/2026 | 7h | **Done** |
| **SCRUM-12**| Trần Đình Trọng | PO | Rà soát điều kiện mốc G0 với PCCOM, tổng hợp báo cáo tiến độ Tuần 02 nộp hệ thống LMS. | 10/11/2026 | 6h | **Done** |
| **TỔNG CỘNG**| **10 Thành viên**| | **Hoàn thành 100% mục tiêu Sprint 1 - Toàn bộ 11 Tasks đã chuyển sang DONE** | | **73h** | **11/11 Done** |

---

## 4. Kết quả Nghiệm Thu Kỹ Thuật Cổng Gate G0 (Week 2 Readiness)

1. **Bộ mô phỏng Virtual Edge Network:** Hệ thống phần mềm đã có thể giả lập hoàn chỉnh mạng lưới 50 cột đèn chiếu sáng và 2 màn hình LED ngoài trời, tự động gửi dữ liệu cảm biến (công suất, nhiệt độ, độ rọi) lên broker MQTT theo đúng chu kỳ.
2. **Giao diện Web Console điều hành trung tâm:** Đã hoạt động tại `http://localhost:8080/index.html`, cho phép người điều hành xem vị trí từng cột đèn trên bản đồ GIS TP.HCM và kéo thanh trượt điều chỉnh độ sáng (Dimming) trực tiếp.
3. **First End-to-End Slice:** Lệnh điều khiển từ Web Console -> Core Backend API -> MQTT Broker -> Virtual Edge Node được xác thực và phản hồi kết quả trong thời gian thực (< 1 giây).
4. **Hạ tầng quản lý đồng bộ:** Kho lưu trữ GitHub và Jira Software đã kết nối chặt chẽ, từng bạn có commit và giờ làm việc cụ thể.

---

## 5. Kế hoạch Tuần 3 (Sprint 2 - Hướng tới Gate G1 Design Approval)
- Hoàn thiện tài liệu kiến trúc kỹ thuật chi tiết (Layered Architecture: Edge, Messaging, Cloud, Web Console).
- Xây dựng mô hình bảo mật (Threat model) theo tiêu chuẩn OWASP ASVS và phân quyền RBAC/MFA.
- Phê duyệt đặc tả Data Contracts (Annex C: Telemetry sample, Command & Result, Content manifest).
- Chuẩn bị kế hoạch tích hợp bo mạch phần cứng ESP32 vật lý vào các Sprint sau (Sprint 3 & 4) khi hệ thống phần mềm đã vận hành ổn định.
