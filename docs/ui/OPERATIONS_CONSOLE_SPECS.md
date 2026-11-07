# Đặc Tả Giao Diện Điều Hành Trung Tâm (Web Operations Console)
**Chịu trách nhiệm:** Bắc Công (`bac21-7`) - Frontend Developer  
**Hồ sơ kỹ thuật:** Mục 6 (Applications and APIs) & DSP 01 - 09

---

## 1. Thành phần giao diện (UI Modules)
1. **Bản đồ số GIS (GIS Map View):**
   - Tích hợp thư viện Leaflet / Mapbox.
   - Hiển thị 50 điểm đèn chiếu sáng tại 2 địa điểm thí điểm (Site 01 & Site 02) kèm mã màu trực quan:
     - Xanh lá: Đang hoạt động bình thường.
     - Vàng: Cảnh báo quá nhiệt hoặc chế độ Offline Fallback.
     - Đỏ: Mất kết nối hoặc ngắt nguồn khẩn cấp.
2. **Bảng điều khiển đèn & Nhóm (Lighting Control Panel):**
   - Thanh trượt chỉnh độ sáng (Dimming Slider 0 - 100%).
   - Nút bật/tắt rơ-le nguồn tổng.
   - Lập lịch thiên văn tự động theo giờ mọc/lặn của mặt trời.
3. **Màn hình LED CMS (LED Content Management):**
   - Quản lý danh sách phát (Playlist), xem trước nội dung (Preview).
   - Quy trình phê duyệt 2 bước (Author -> Approver -> Publisher theo DSP 03).
