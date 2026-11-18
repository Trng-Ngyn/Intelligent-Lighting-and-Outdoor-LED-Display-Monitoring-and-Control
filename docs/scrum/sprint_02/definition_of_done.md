# Scrum Definition of Done (DoD) & Cadence

**Chịu trách nhiệm:** Lê Hoàng Thanh (`thanhlh05`) – Scrum Master
**Áp dụng:** Dự án Intelligent Lighting and Outdoor LED Display Monitoring and Control (Sprint 1 – 8)
**Cập nhật lần này:** Sprint 2 (Tuần 3 và 4) – Gate G1 Design Approval, ngày 14/11/2026

---

## 1. Definition of Done (DoD) Checklist chung

Mỗi User Story / Task trên Jira được coi là hoàn tất (`Done`) khi thỏa mãn các điều kiện:

- **Mã nguồn:** Code sạch, tuân thủ quy chuẩn đặt tên biến, comment rõ ràng logic xử lý phức tạp.
- **Kiểm thử cục bộ:** Đã chạy thử nghiệm trên máy hoặc giả lập, không có lỗi runtime/compile.
- **Review nội bộ:** Được ít nhất 1 thành viên (hoặc Technical Lead / PO) review và phê duyệt.
- **Tài liệu hóa:** Cập nhật README hoặc tài liệu thiết kế liên quan nếu có thay đổi interface/schema.
- **Truy vết:** Commit message phải chứa mã Jira Task tương ứng (ví dụ: `feat(iot): ... [SCRUM-6]`).
- **Deployable:** Tương thích với môi trường CI/CD và không làm gián đoạn nhánh `main`.

---

## 2. DoD bổ sung cho Sprint 2 – Gate G1 (hồ sơ thiết kế)

Sprint 2 chủ yếu tạo **tài liệu thiết kế**, nên mỗi sản phẩm thiết kế chỉ được kéo sang `Done` khi đạt thêm các điều kiện:

- [ ] Có **link** tới tài liệu hoặc commit trên Git (ghi vào ticket Jira).
- [ ] Schema / data contract được **validate**, không còn lỗi.
- [ ] Được đưa vào **ma trận RTM** của QA (nếu liên quan).
- [ ] Trạng thái Jira được cập nhật và **giờ làm ghi đúng ngày làm thật**.
- [ ] **PO chấp nhận** theo tiêu chí hoàn thành của ticket.


---

## 3. Tiêu chí hoàn thành theo từng ticket Sprint 2 (lấy từ Jira)

| Ticket | Người nhận | Tiêu chí hoàn thành |
|---|---|---|
| SCRUM-13 [PO] | Trần Đình Trọng | Đặc tả quy trình duyệt nội dung LED; bảng ngưỡng an toàn quang học; tài liệu phân loại quyền duyệt tích hợp vào tài liệu kiến trúc |
| SCRUM-14 [SM] | Lê Hoàng Thanh | Mọi Daily có ghi chú; bảng DoD được 10 người xác nhận; tiến độ Sprint > 90% |
| SCRUM-15 [TL] | Trần Nhật Hào | Tài liệu kiến trúc (SAD) và sơ đồ thành phần; Threat Model ASVS cấp 2 được rà soát; hướng dẫn chứng chỉ mTLS |
| SCRUM-16 [IoT] | Bùi Mai Khánh Kiệt | Đặc tả MQTT Topic Taxonomy và header MQTT 5; simulator chạy đúng topic mớ |
| SCRUM-17 [IoT] | Nguyễn Tấn Vượng | Module dimming an toàn qua unit test; mô phỏng bảo vệ nhiệt và fallback offline |
| SCRUM-18 [DE] | Lê Tiến Công | File DDL (.sql); JSON Schema xác thực payload và từ chối gói sai cấu trúc |
| SCRUM-19 [BE] | Trần Hoài Nguyên Vỹ | `openapi.yaml` validate không warning; mock API phản hồi đúng cho Frontend |
| SCRUM-20 [ML] | Đặng Nguyễn Minh Phi | Fault Taxonomy và Labeling Protocol; kiến trúc pipeline AI baseline được rà soát |
| SCRUM-21 [FE] | Đinh Nguyễn Công Bắc | Bộ wireframe hoàn chỉnh; prototype thao tác điều khiển dưới 3 lần bấm |
| SCRUM-22 [QA] | Nguyễn Đại Phước | Ma trận RTM bao phủ 100% tiêu chí liên quan; Test Protocol được phê duyệt |
| SCRUM-23 [PO] | Trần Đình Trọng | Hồ sơ G1 được thẩm định; đủ điều kiện mở Sprint 3 |

---

## 4. Quy chế họp Scrum (Section 11 RFP)

- **Daily Scrum:** 09:00 – 09:15 hàng ngày trên Google Meet (15 phút: hôm qua làm gì, hôm nay làm gì, có rào cản gì không). Ghi chú ngắn mỗi ngày: số người có mặt, rào cản, việc chính.
- **Sprint Planning:** RFP đề xuất 09:30 – 12:30 Thứ Hai tuần lẻ đầu Sprint. Sprint 2 họp ngày 13/11/2026, 20:00 – 22:00.
- **Backlog Refinement:** 14:00 – 15:00 Thứ Tư hàng tuần (Sprint 2: 18/11/2026).
- **Sprint Review & Retrospective:** RFP đề xuất 13:30 – 16:15 Thứ Sáu tuần chẵn cuối Sprint. Ngày cụ thể Sprint 2: [chốt tại Refinement 18/11].
- **Cập nhật Jira:** trước 23:59 mỗi ngày.
