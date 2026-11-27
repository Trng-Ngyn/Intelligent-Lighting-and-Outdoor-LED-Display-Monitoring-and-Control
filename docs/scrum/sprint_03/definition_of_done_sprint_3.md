# Definition of Done (DoD) – Sprint 3

* **Chịu trách nhiệm:** Lê Hoàng Thanh (`thanhlh05`) – Scrum Master
* **Áp dụng:** Sprint 3 (Tuần 5 & 6) – Gate G2 Integrated Pilot
* **Ngày cập nhật:** 25/11/2026

---

## 1. Definition of Done chung (áp dụng mọi ticket)

Một ticket chỉ được kéo sang trạng thái **Done** khi thỏa mãn đầy đủ các tiêu chí sau:

- [ ] Code sạch, tuân thủ quy chuẩn đặt tên, có comment rõ ràng cho các logic phức tạp.
- [ ] Đã chạy thử nghiệm trên máy / giả lập / phần cứng thật (nếu liên quan), không còn lỗi runtime/compile.
- [ ] Được ít nhất 1 thành viên (hoặc TL / PO) review và phê duyệt.
- [ ] Tài liệu liên quan (README, đặc tả, schema) đã được cập nhật.
- [ ] Commit message chứa mã Jira (ví dụ: `feat(iot): flash mTLS [SCRUM-27]`).
- [ ] Tương thích CI/CD, không làm hỏng nhánh `main`.
- [ ] Trạng thái Jira và thời gian làm việc (worklog) được cập nhật đúng ngày thực tế.

---

## 2. DoD bổ sung riêng cho Sprint 3 – Gate G2 (tích hợp phần cứng)

Vì Sprint 3 tập trung vào tích hợp thực tế, mỗi sản phẩm phải đạt thêm các yêu cầu sau:

- [ ] Có bằng chứng chạy trên phần cứng thật hoặc môi trường Staging (log, ảnh chụp, video ngắn, số liệu đo).
- [ ] Telemetry / lệnh điều khiển đi đúng chuẩn Annex C và topic MQTT 5 đã thống nhất.
- [ ] Được đưa vào ma trận RTM và kịch bản HIL của QA (nếu liên quan).
- [ ] Các chỉ số SLA cốt lõi được đo và ghi nhận (độ trễ, tỷ lệ mất gói, thời gian kích hoạt bảo vệ…).
- [ ] PO chấp nhận theo Acceptance Criteria của ticket.

---

## 3. Tiêu chí hoàn thành theo từng ticket Sprint 3

| Ticket | Người nhận | Tiêu chí hoàn thành chính |
| :--- | :--- | :--- |
| **SCRUM-24** | Trần Đình Trọng | Biên bản nghiệm thu G1 có chữ ký; danh mục thiết bị Lab sẵn sàng; Backlog Sprint 3 đã phân bổ 100%. |
| **SCRUM-25** | Lê Hoàng Thanh | Biên bản Planning 3 + Sprint Goal đã công bố; 100% thành viên cập nhật Daily đúng giờ & format; tỷ lệ xử lý blocker < 24h ≥ 95%. |
| **SCRUM-26** | Trần Nhật Hào | Staging online 24/7 (Mosquitto TLS 8883 + TimescaleDB + FastAPI); CI/CD build firmware & Docker thành công 100% trên mọi PR. |
| **SCRUM-27** | Bùi Mai Khánh Kiệt | ESP32 kết nối mTLS thành công; telemetry chạy liên tục ≥ 4 giờ không rớt kết nối / tràn Heap. |
| **SCRUM-28** | Nguyễn Tấn Vượng | Dimming mượt trên Driver thật; Thermal Derating & Offline Fallback kích hoạt đúng ngưỡng; có unit test + demo phần cứng. |
| **SCRUM-29** | Lê Tiến Công | Ingestion Service ghi đúng Hypertables theo Annex C; Continuous Aggregate chạy ổn với dữ liệu thật. |
| **SCRUM-30** | Trần Hoài Nguyên Vỹ | Core REST API (CRUD + JWT/RBAC + Dimming) hoạt động; có OpenAPI cập nhật và test Postman/cURL. |
| **SCRUM-31** | Đinh Nguyễn Công Bắc | Web Console hiển thị dữ liệu telemetry thật trên bản đồ Leaflet; thao tác điều khiển cơ bản hoạt động. |
| **SCRUM-32** | Đặng Nguyễn Minh Phi | Microservice Docker latency < 150 ms / batch 50 mẫu; phát hiện F01 & F02 ≥ 90% trên tập mô phỏng sự cố. |
| **SCRUM-33** | Nguyễn Đại Phước | Báo cáo HIL Test đầy đủ số liệu; độ trễ điều khiển < 1.5 s; Load test 200 msg/s đạt yêu cầu; tỷ lệ mất gói < 0.1%. |

---

## 4. Quy chế họp & cập nhật (giữ nguyên + điều chỉnh nhẹ)

* **Daily Scrum:** Trả lời 3 câu hỏi mỗi ngày.
* **Cập nhật Jira:** Hoàn tất cập nhật trạng thái và log thời gian trước **23:59** hàng ngày.
