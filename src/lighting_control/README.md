# Lighting Control Modules – Subtask 1

Bộ điều khiển thuần Python dùng cho mô phỏng/tham chiếu và unit test. Firmware ESP32 có các module C++ tương ứng tại `src/firmware_esp32/`.

## Các module

| Module | Trách nhiệm | Quy tắc đã triển khai |
|---|---|---|
| `dali.controller` | Quản lý thiết bị DALI theo short/group/broadcast address, gửi arc-power và cấu hình native fade | Hỗ trợ nhiều driver; kiểm tra min/max; không đánh đồng gửi frame với xác minh ánh sáng vật lý; từ chối điều khiển nếu chưa cấu hình bộ chuyển đổi arc-power |
| `fade.controller` | Chọn preset và yêu cầu driver thực hiện fade | Preset 1: DALI setting 5 (~2.8s); preset 2: setting 6 (4.0s); preset 3: setting 7 (5.7s). Cấu hình fade trước, sau đó gửi target brightness; không tạo fade bằng PWM phần mềm |
| `thermal.engine` | Giám sát nhiệt độ và tính giới hạn độ sáng | Trên 75°C: brightness = yêu cầu gốc × 0.8; trên 90°C: shutdown; dưới 75°C liên tục 300s mới xóa latch shutdown; nhiệt độ >=75°C reset bộ đếm hồi phục |
| `offline.fallback` | Lịch hoạt động khi MQTT mất kết nối | Chỉ kích hoạt khi mất MQTT >300s; 18:00–22:00 100%, 22:00–00:00 70%, 00:00–05:00 40%, 05:00–05:30 dùng lux với hysteresis 50/80 lux trong 120s; ngoài khung hoạt động OFF |

## Hợp đồng kết quả

Mỗi module trả `ModuleResult` với các trường:

- `module`, `status`, `state`, `timestamp`
- `input`, `output`, `diagnostics`
- `error` gồm `code`, `message`, `severity`, `recoverable`, `details`

Các trạng thái lỗi cảm biến/RTC không được tự đổi thành số đo mặc định. Kết quả được giữ đầy đủ để Safety Supervisor quyết định safe fallback, giới hạn hoặc shutdown.

## DALI hardware boundary

`DaliBus`/`IDaliBus` là interface của lớp truyền dẫn. Phần cứng cần transceiver DALI tương thích và adapter triển khai timing/Manchester đúng chuẩn. Chưa có sơ đồ transceiver/chân bus trong repository, do đó Subtask 1 **không giả lập một bus DALI thật và không tự gán GPIO PWM thành DALI**. Bộ chuyển đổi brightness phần trăm sang arc-power được inject qua `arc_power_mapper`/`IArcPowerMapper`; đặc tả đường cong sẽ được khóa ở Subtask 3.

Firmware hiện tại trong `main.cpp` vẫn là luồng cũ dùng PWM; các module C++ mới được tách độc lập, chờ Safety Supervisor và adapter DALI phần cứng trước khi nối vào luồng điều khiển chính. Không dùng firmware PWM hiện tại để nghiệm thu DALI.

## Chạy unit test

Từ thư mục gốc repository:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```
