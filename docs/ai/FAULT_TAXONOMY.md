# Phân Loại Sự Cố Thiết Bị & Khung Phát Hiện Bất Thường (AI 02)
**Chịu trách nhiệm:** Minh Phi (`minhphi1012`) - ML Developer  
**Hồ sơ kỹ thuật:** Mục 5 (AI 02) & Annex E (EVAL 01 - EVAL 02)

---

## 1. Phân loại sự cố (Fault Taxonomy)
Bộ dữ liệu bất thường phân tách làm 4 nhóm sự cố chính:
1. **F01 - Mất nguồn đột ngột / Hỏng Driver (Sudden Driver Outage):** Điện áp V = 0 hoặc I = 0 khi rơ-le đang ở trạng thái ON và lệnh Dimming > 0.
2. **F02 - Kẹt trạng thái (Stuck State):** Không phản hồi thay đổi độ sáng dù đã nhận lệnh điều khiển.
3. **F03 - Quá nhiệt (Overheating):** Nhiệt độ hoạt động liên tục vượt ngưỡng 75°C trong hơn 5 phút.
4. **F04 - Mất đồng bộ / Mất kết nối (Communication Loss):** Quá 180 giây không nhận được gói tin nhịp tim (Heartbeat/Telemetry).

---

## 2. Tiêu chuẩn đánh giá mô hình (AT 06)
- **Precision:** $\ge 85\%$ trên tập kiểm thử độc lập (30 positive episodes).
- **Recall:** $\ge 90\%$ trên tập kiểm thử độc lập.
- **Nuisance Rate:** Không quá 1 cảnh báo sai / thiết bị / tuần.
