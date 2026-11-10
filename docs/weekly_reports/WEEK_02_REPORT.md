# BÁO CÁO TIẾN ĐỘ HÀNG TUẦN - TUẦN 02 (WEEKLY REPORT 02)
**Học phần:** Đồ án Học kỳ Doanh nghiệp  
**Dự án:** Intelligent Lighting and Outdoor LED Display Monitoring and Control  
**Doanh nghiệp tiếp nhận:** CÔNG TY TNHH KỸ THUẬT TIN HỌC PHÚC CHÂU (PCCOM CO., LTD)  
**Mô hình áp dụng:** Agile Scrum (Sprint 1: Weeks 1 - 2 | Cổng nghiệm thu: Gate G0 Readiness)  
**Jira Workspace:** https://hockidoanhnghiep.atlassian.net (Project Key: SCRUM)  
**GitHub Repository:** https://github.com/Trng-Ngyn/Intelligent-Lighting-and-Outdoor-LED-Display-Monitoring-and-Control  
**Hạn chót nộp LMS:** Thứ Tư, 11/11/2026, 12:00 AM  

---

## 1. Cơ cấu Nhóm Scrum & Phân chia 10 Vai trò (RFP Section 11)

| STT | Họ tên / Tài khoản | Vai trò trong nhóm Scrum | Nhiệm vụ chính trong dự án | Mã Task phụ trách |
| :---: | :--- | :--- | :--- | :---: |
| 1 | **Trần Đình Trọng** | **Product Owner (PO) & Team Leader** | **Vai trò cao nhất:** Định nghĩa Product Goal; phân loại và ưu tiên Product Backlog; đại diện làm việc và nghiệm thu với PCCOM CO., LTD; ký nghiệm thu các mốc G0 - G4. | `SCRUM-1`<br/>`SCRUM-12` |
| 2 | Thành viên 2 | **Scrum Master (SM)** | Tổ chức các sự kiện Scrum (Daily Scrum 09:00 hàng ngày, Sprint Planning, Review & Retro); theo dõi tiến độ trên Jira; gỡ vướng mắc quy trình. | `SCRUM-7` |
| 3 | Thành viên 3 | **Technical Lead & DevOps** | Thiết kế kiến trúc tổng thể IoT/Cloud; thiết lập CI/CD pipeline, Git repository, áp dụng chuẩn bảo mật OWASP ASVS và NIST IR 8259A. | `SCRUM-5` |
| 4 | Thành viên 4 | **IoT & Edge Developer** | Lập trình gateway/controller; tích hợp giao thức DALI/D4i, Zhaga; xây dựng cơ chế lưu đệm telemetry offline 24h và local fallback khi mất kết nối cloud. | `SCRUM-6`<br/>`SCRUM-3` |
| 5 | Thành viên 5 | **Data Engineering Developer** | Thiết kế luồng thu thập dữ liệu đo đạc (telemetry: W, Wh, lux, nhiệt độ); xây dựng pipeline lưu trữ Time-Series và chuẩn hóa dữ liệu theo Annex C. | `SCRUM-8` |
| 6 | Thành viên 6 | **ML Developer 1** | Xây dựng thuật toán điều khiển ánh sáng thích ứng theo cảm biến quang học/lưu lượng (AI 01) và phân tích tối ưu điện năng (AI 03). | `SCRUM-9` |
| 7 | Thành viên 7 | **ML Developer 2** | Nghiên cứu và huấn luyện mô hình phát hiện bất thường thiết bị/hệ thống mạng (AI 02); chuẩn bị bộ kiểm thử đạt Precision ≥85%, Recall ≥90% (AT 06). | `SCRUM-9` |
| 8 | Thành viên 8 | **Backend Developer** | Xây dựng Core API service, dịch vụ quản lý trạng thái thiết bị, phân quyền RBAC/MFA, quy trình phê duyệt phát hành nội dung LED đa tầng (DSP 02-04). | `SCRUM-4` |
| 9 | Thành viên 9 | **Frontend Developer** | Phát triển Giao diện điều hành trung tâm (Web Operations Console), hiển thị bản đồ số GIS, quản lý thư viện nội dung màn hình LED và dashboard năng lượng. | `SCRUM-10` |
| 10 | Thành viên 10 | **QA Engineering Developer** | Xây dựng kịch bản kiểm thử tự động cho 12 tiêu chí nghiệm thu (AT 01 - AT 12); quản lý ma trận truy vết (RTM) liên kết giữa yêu cầu và mã nguồn. | `SCRUM-11` |

---

## 2. Mục tiêu Sprint 1 (Sprint Goal)
> **Sprint Goal:** Thiết lập toàn diện hạ tầng phát triển (Jira Scrum, GitHub Repository, CI/CD); hoàn thiện khảo sát phạm vi Pilot (2 địa điểm, 50 điểm chiếu sáng, 2 màn hình LED ngoài trời); vượt qua cổng kiểm tra tính khả thi kỹ thuật **Gate G0 Readiness**.

---

## 3. Chi tiết Công việc Đã Thực Hiện & Nhật Ký Log Work (Sprint 1: Tuần 1 - Tuần 2)

Nhóm đã ghi nhận tổng cộng **73 giờ làm việc thực tế** trên hệ thống Jira Software:

| Mã Task Jira | Vai trò | Tóm tắt công việc đã thực hiện | Thời gian bắt đầu | Giờ đã log |
| :---: | :---: | :--- | :---: | :---: |
| **SCRUM-1** | PO | Khảo sát 2 site, 50 điểm đèn, 2 màn hình LED; xác định phạm vi 4 Package và khởi tạo Backlog. | 02/11/2026 | 8h |
| **SCRUM-7** | SM | Tổ chức Sprint Planning 1, thống nhất DoD, phân bổ năng lực (40h/tuần/dev) và lịch Daily 09:00. | 28/10/2026 | 4h |
| **SCRUM-5** | TL | Khởi tạo Git repo, chuẩn bảo mật OWASP ASVS mức 2, pipeline build/test và cấu hình Jira Scrum board. | 30/10/2026 | 8h |
| **SCRUM-6** | IoT | Xây dựng mock gateway và kiểm tra gửi telemetry mẫu 1 KiB/phút lên broker MQTT 5 (End-to-End Slice). | 31/10/2026 | 8h |
| **SCRUM-8** | DE | Hoàn thành Data Schema (W, Wh, V, A, lux, °C) theo Annex C và kiểm tra ingestion pipeline Time-Series. | 05/11/2026 | 7h |
| **SCRUM-9** | ML | Xây dựng taxonomy lỗi thiết bị và mô hình rule-based phát hiện bất thường ban đầu (AI 02). | 06/11/2026 | 8h |
| **SCRUM-3** | IoT | Bench test bộ điều khiển thực địa D4i/Zhaga; thực thi thành công lệnh dimming an toàn đầu tiên. | 06/11/2026 | 6h |
| **SCRUM-4** | BE | Xây dựng cơ chế tải trước và kích hoạt danh sách phát (cached display playlist) khi mất kết nối mạng. | 06/11/2026 | 5h |
| **SCRUM-10** | FE | Thiết kế wireframe Dashboard và tích hợp bản đồ số GIS hiển thị 50 vị trí cột đèn thí điểm. | 07/11/2026 | 6h |
| **SCRUM-11** | QA | Xây dựng ma trận truy vết RTM kết nối LGT/DSP với bộ test AT 01-12; kịch bản nghiệm thu Cổng G0. | 09/11/2026 | 7h |
| **SCRUM-12** | PO | Rà soát điều kiện mốc G0 với PCCOM, tổng hợp báo cáo tiến độ Tuần 02 nộp hệ thống LMS. | 10/11/2026 | 6h |
| **TỔNG CỘNG**| | **Đã phân bổ và log work đầy đủ cho 10 vị trí theo đúng tiến độ WBS** | | **73h** |

---

## 4. Kết quả Đạt Được Đối Soát Theo Cổng Gate G0 (Week 2 Readiness)

1. **Khảo sát phạm vi & Tương thích phần cứng:** Xác định rõ 2 site triển khai, đặc tả kỹ thuật 50 bộ đèn tích hợp DALI/D4i và 2 màn hình LED ngoài trời.
2. **First End-to-End Slice:** Đã gửi thành công lệnh điều khiển an toàn đầu tiên từ Cloud xuống Edge có cơ chế giới hạn dòng điện và bảo vệ vật lý.
3. **Màn hình LED Offline Fallback:** Thử nghiệm danh sách phát lưu đệm thành công, đảm bảo không phát màn hình đen khi ngắt WAN/Cloud trong 24h.
4. **Hạ tầng quản lý:** Hoàn tất kết nối hệ thống Jira Scrum với đầy đủ backlog, worklog và kho lưu trữ GitHub đồng bộ.

---

## 5. Kế hoạch Tuần 3 (Sprint 2 - Hướng tới Gate G1 Design Approval)
- Hoàn thiện tài liệu kiến trúc kỹ thuật chi tiết (Layered Architecture: Edge, Messaging, Cloud, Web Console).
- Xây dựng mô hình bảo mật (Threat model) theo tiêu chuẩn OWASP ASVS và phân quyền RBAC/MFA.
- Phê duyệt đặc tả Data Contracts (Annex C: Telemetry sample, Command & Result, Content manifest).
- Lập trình giao diện Web Console điều hành trung tâm và kết nối API RESTful.
