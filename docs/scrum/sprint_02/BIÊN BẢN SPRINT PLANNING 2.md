# BIÊN BẢN SPRINT PLANNING 2

| Mục | Nội dung |
| :--- | :--- |
| **Sprint** | Sprint 2 (Tuần 3 và 4) – Gate G1 Design Approval |
| **Ngày họp** | 13/11/2026 |
| **Thời gian** | 20:00 đến 22:00 (120 phút) |
| **Hình thức** | Google Meet |
| **Thời gian Sprint** | 11/11/2026 đến 24/11/2026 |
| **Điều phối và ghi biên bản** | Lê Hoàng Thanh (Scrum Master) |
| **Product Owner** | Trần Đình Trọng |
| **Có mặt** | 9/10 |
| **Vắng mặt** | Nguyễn Tấn Vượng |

---

## 1. Sprint Goal
Hoàn thiện toàn diện Hồ sơ thiết kế kiến trúc phần mềm đa tầng (SAD), Mô hình đe dọa an ninh mạng theo chuẩn OWASP ASVS Cấp 2, Bộ Data Contracts & Schema TimescaleDB, Giao thức gán nhãn AI Baseline, và Wireframes Web Console GIS hướng tới thẩm định Cổng Gate G1 Design Approval với Doanh nghiệp.

## 2. Bối cảnh
* **Cổng liên quan:** G1 (thiết kế), theo RFP là tuần 4.
* **Bằng chứng G1 theo RFP gồm 8 hạng mục:** kiến trúc; threat model; giới hạn trắc quang và màn hình; schema và data contract; backlog Sprint 3 và 4; giao thức kiểm thử và RTM; baseline và giao thức gán nhãn; ma trận giao diện đã ký.
* **Backlog Sprint 2:** gồm 11 ticket (`SCRUM-13` đến `SCRUM-23`), do PO soạn từ yêu cầu RFP và tạo trên Jira trước buổi họp. Tại họp, nhóm rà soát nội dung, người nhận và ước lượng của từng ticket.
* **Đề tài:** hệ thống điều hành giám sát và điều khiển từ xa đèn chiếu sáng ngoài trời và màn hình LED ngoài trời.

## 3. Năng lực nhóm (Capacity)

| Thành viên | Vai trò | Ước lượng Jira (giờ) |
| :--- | :--- | :---: |
| Trần Đình Trọng | PO (`SCRUM-13`, `23`) | 30 |
| Lê Hoàng Thanh | SM (`SCRUM-14`) | 10 |
| Trần Nhật Hào | TL & DevOps (`SCRUM-15`) | 24 |
| Bùi Mai Khánh Kiệt | IoT & Edge (`SCRUM-16`) | 18 |
| Nguyễn Tấn Vượng | IoT & Edge (`SCRUM-17`) | 16 |
| Lê Tiến Công | Data Engineering (`SCRUM-18`) | 22 |
| Trần Hoài Nguyên Vỹ | Backend (`SCRUM-19`) | 20 |
| Đặng Nguyễn Minh Phi | ML (`SCRUM-20`) | 22 |
| Đinh Nguyễn Công Bắc | Frontend (`SCRUM-21`) | 16 |
| Nguyễn Đại Phước | QA (`SCRUM-22`) | 18 |
| **Tổng** | | **196** |

## 4. Sprint Backlog đã chọn (theo Jira)
**Tổng:** 11 ticket, 65 story point, khoảng 196 giờ ước lượng.

| Ticket | Nội dung | Người nhận | SP | Ước lượng |
| :--- | :--- | :--- | :---: | :---: |
| `SCRUM-13` | W3-PO Đặc tả luồng phê duyệt nội dung LED đa tầng và quy chuẩn an toàn chiếu sáng | Trần Đình Trọng | 5 | 16h |
| `SCRUM-14` | W3-SM Điều phối Sprint 2, giám sát DoD G1 | Lê Hoàng Thanh | 3 | 10h |
| `SCRUM-15` | W3-TL Kiến trúc phần mềm đa tầng và threat model OWASP ASVS cấp 2 | Trần Nhật Hào | 8 | 24h |
| `SCRUM-16` | W3-IoT Chuẩn giao tiếp Edge-to-Cloud và MQTT topic taxonomy | Bùi Mai Khánh Kiệt | 5 | 18h |
| `SCRUM-17` | W4-IoT Thuật toán dimming an toàn, giới hạn quang học, đường cong DALI | Nguyễn Tấn Vượng | 5 | 16h |
| `SCRUM-18` | W3-DE Cơ sở dữ liệu TimescaleDB/PostgreSQL và data contract Annex C | Lê Tiến Công | 8 | 22h |
| `SCRUM-19` | W4-BE OpenAPI, RBAC, workflow duyệt nội dung LED | Trần Hoài Nguyên Vỹ | 8 | 20h |
| `SCRUM-20` | W3-ML Giao thức gán nhãn và kiến trúc AI baseline phát hiện bất thường F01 đến F04 | Đặng Nguyễn Minh Phi | 8 | 22h |
| `SCRUM-21` | W3-FE Wireframe UI/UX Web Operations Console GIS và dashboard năng lượng | Đinh Nguyễn Công Bắc | 5 | 16h |
| `SCRUM-22` | W4-QA Giao thức kiểm thử chấp nhận G1 và mở rộng ma trận RTM | Nguyễn Đại Phước | 5 | 18h |
| `SCRUM-23` | W4-PO Tổng hợp hồ sơ G1 và điều phối thẩm định với PCCOM | Trần Đình Trọng | 5 | 14h |

## 5. Phụ thuộc giữa các việc
* **BE (`SCRUM-19`)** cần schema của DE (`SCRUM-18`) và topic MQTT của IoT (`SCRUM-16`).
* **FE (`SCRUM-21`)** cần mock API từ BE (`SCRUM-19`).
* **QA (`SCRUM-22`)** cần đầu ra của hầu hết ticket khác để lập RTM.
* **PO (`SCRUM-23`)** tổng hợp hồ sơ G1 từ tất cả ticket.
* **Mốc nội bộ nhóm thống nhất:** các tài liệu thành phần (`SCRUM-15`, `16`, `17`, `18`, `19`, `20`, `21`) hoàn thành chậm nhất **20/11**; QA lập RTM và PO tổng hợp hồ sơ G1 trong **21/11 đến 22/11**.

## 6. Rủi ro và vướng mắc

| Mã | Mô tả | Ảnh hưởng | Người xử lý |
| :--- | :--- | :--- | :--- |
| **IMP-01** | Nguyễn Tấn Vượng vắng buổi họp; `SCRUM-17` (To Do) chưa được xác nhận nội dung và ước lượng trực tiếp | Có thể trễ phần dimming và fallback | SM và Nguyễn Tấn Vượng |

## 7. Lịch làm việc đã thống nhất
* **Daily Scrum:** 09:00 đến 09:15 trên Google Meet.
* **Backlog Refinement:** Thứ Tư 18/11/2026, 14:00 đến 15:00.
* **Sprint Review:** Thứ Sáu tuần chẵn 13:30 đến 15:00.
* **Retrospective:** Thứ Sáu tuần chẵn 15:15 đến 16:15.
* **Cập nhật Jira:** Trước 23:59 giờ mỗi ngày.