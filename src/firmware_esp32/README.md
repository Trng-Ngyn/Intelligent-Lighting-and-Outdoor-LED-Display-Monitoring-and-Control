# ESP32 Lighting Controller Firmware

> **Phân hệ:** Package A - Lighting Operations (LGT 01 - LGT 08)  
> **Nền tảng:** ESP32-WROOM-32 / ESP32-S3  
> **Framework:** Arduino / PlatformIO / ESP-IDF  

---

## 📌 Tính năng đáp ứng Hồ sơ kỹ thuật (RFP)
1. **Thu thập Telemetry chuẩn Annex C (DAT 01):** Định kỳ 60 giây gửi các thông số: công suất tiêu thụ (`W`), điện năng tích lũy (`Wh`), điện áp (`V`), dòng điện (`A`), hệ số công suất (`power_factor`), nhiệt độ bóng đèn (`°C`) và cường độ sáng môi trường (`lux`).
2. **Thực thi lệnh điều khiển từ xa an toàn (LGT 02, CTL 01, CTL 02):**
   - Hỗ trợ lệnh điều chỉnh độ sáng `DIM` (0 - 100% qua PWM) và `SWITCH` (đóng/ngắt rơ-le nguồn).
   - Kiểm tra hạn lệnh (`expires_at`), chống thực thi lệnh cũ/lệnh lặp (Replay protection).
   - Gửi phản hồi kết quả thực thi (`status: EXECUTED / REJECTED / EXPIRED`) kèm giá trị thực tế quan sát được về Cloud.
3. **Chế độ tự hành khi mất kết nối mạng (OPS 02, CTL 04):** Khi mất kết nối Cloud/MQTT quá 180s, thiết bị tự động chuyển sang chế độ fallback cục bộ: tự động tăng/giảm độ sáng dựa theo cảm biến quang học (LDR) mà không bị gián đoạn hoạt động.
4. **Bảo vệ phần cứng độc lập (LGT 06, LGT 07):**
   - Giảm độ sáng tự động khi nhiệt độ vượt ngưỡng cảnh báo (Thermal Derating ≥ 75°C).
   - Ngắt rơ-le khẩn cấp bảo vệ bóng đèn khi nhiệt độ nguy hiểm (≥ 85°C).

---

## 🔌 Sơ đồ đấu nối chân (Pinout Mapping)

| Linh kiện / Chức năng | Chân ESP32 | Ghi chú kỹ thuật |
| :--- | :---: | :--- |
| **PWM Dimming Output** | **GPIO 18** | Tần số 5kHz, độ phân giải 8-bit (nối vào Driver LED DIM 0-10V hoặc MOSFET) |
| **Rơ-le Cắt Nguồn (Relay)** | **GPIO 23** | Điều khiển cuộn hút rơ-le 220VAC cắt nguồn tổng khi khẩn cấp |
| **Cảm biến Ánh sáng (LDR)** | **GPIO 34** | Chân Analog (ADC1_CH6), đọc giá trị lux môi trường |
| **Cảm biến Nhiệt độ (DHT/DS)**| **GPIO 4** | Giám sát nhiệt độ bên trong vỏ đèn |
| **Đèn LED báo trạng thái** | **GPIO 2** | Sáng khi kết nối MQTT thành công, nhấp nháy khi mất mạng |

---

## 🚀 Hướng dẫn nạp code (Flash Firmware)

### Cách 1: Nạp qua PlatformIO (VS Code)
1. Cài đặt extension **PlatformIO IDE** trên VS Code.
2. Mở thư mục `src/firmware_esp32`.
3. Chỉnh sửa `WIFI_SSID` và `WIFI_PASSWORD` trong file [`include/config.h`](include/config.h).
4. Cắm cáp Micro-USB / Type-C nối ESP32 với máy tính.
5. Bấm nút **Build (✔)** và **Upload (➡)** trên thanh công cụ của PlatformIO.

### Cách 2: Nạp qua Arduino IDE
1. Cài đặt board **esp32 by Espressif Systems** trong Boards Manager.
2. Cài đặt các thư viện cần thiết trong Library Manager:
   - `ArduinoJson` (v6.x)
   - `PubSubClient`
3. Đổi tên file [`src/main.cpp`](src/main.cpp) thành `firmware_esp32.ino` và mở bằng Arduino IDE.
4. Chọn Board: **ESP32 Dev Module**, chọn đúng Cổng COM và bấm **Upload**.

---

## 📡 Cấu trúc Topic MQTT
- **Gửi Telemetry (ESP32 -> Cloud):** `pccom/lighting/SITE_01/LGT_NODE_001/telemetry`
- **Nhận Lệnh (Cloud -> ESP32):** `pccom/lighting/SITE_01/LGT_NODE_001/command`
- **Báo cáo Kết quả (ESP32 -> Cloud):** `pccom/lighting/SITE_01/LGT_NODE_001/result`
