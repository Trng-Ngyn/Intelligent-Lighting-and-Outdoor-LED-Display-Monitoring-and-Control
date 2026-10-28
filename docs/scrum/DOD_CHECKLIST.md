# Scrum Definition of Done (DoD) & Cadence
**Chịu trách nhiệm:** Thanh Lê (`thanhlh05`) - Scrum Master  
**Áp dụng:** Dự án Intelligent Lighting and Outdoor LED Display Monitoring and Control (Sprint 1 - 8)

---

## 1. Definition of Done (DoD) Checklist
Mỗi User Story / Task trên Jira được coi là hoàn tất (`Done`) khi thỏa mãn các điều kiện:
- [ ] **Mã nguồn:** Code sạch, tuân thủ quy chuẩn đặt tên biến, comment rõ ràng logic xử lý phức tạp.
- [ ] **Kiểm thử cục bộ:** Đã chạy thử nghiệm trên máy hoặc giả lập, không có lỗi runtime/compile.
- [ ] **Review nội bộ:** Được ít nhất 1 thành viên (hoặc Technical Lead / PO) review và phê duyệt.
- [ ] **Tài liệu hóa:** Cập nhật README hoặc tài liệu thiết kế liên quan nếu có thay đổi interface/schema.
- [ ] **Truy vết:** Commit message phải chứa mã Jira Task tương ứng (ví dụ: `feat(iot): ... [SCRUM-6]`).
- [ ] **Deployable:** Tương thích với môi trường CI/CD và không làm gián đoạn nhánh `main`.

---

## 2. Quy chế Họp Scrum (Section 11 RFP)
- **Daily Scrum:** 09:00 - 09:15 hàng ngày (15 phút: hôm qua làm gì, hôm nay làm gì, có rào cản gì không).
- **Sprint Planning:** 09:30 - 12:30 Thứ Hai tuần lẻ đầu Sprint.
- **Backlog Refinement:** 14:00 - 15:00 Thứ Tư hàng tuần.
- **Sprint Review & Retrospective:** 13:30 - 16:15 Thứ Sáu tuần chẵn cuối Sprint.
