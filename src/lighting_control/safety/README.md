# Safety Supervisor

## 1. Vai trò

`SafetySupervisor` là lớp ra quyết định trung tâm. Nó tiếp nhận yêu cầu độ sáng, giới hạn lịch, trạng thái cảm biến, kết quả các module và trạng thái truyền dẫn; sau đó tạo `SafetyDecision`. Module này **không tự gửi frame DALI**. `main.cpp`/lớp tích hợp chịu trách nhiệm gọi Supervisor trước khi chuyển quyết định hợp lệ đến Fade Controller và DALI Controller.

## 2. Thành phần

| Thành phần | File | Trách nhiệm |
|---|---|---|
| Safety Supervisor | `supervisor.py` | Thu thập dữ liệu, tạo snapshot lỗi và gọi Decision Engine |
| Fault Manager | `fault_manager.py` | Quản lý lỗi theo mã, mức độ, nguồn, thời gian và khả năng phục hồi |
| Decision Engine | `decision_engine.py` | Áp dụng thứ tự ưu tiên và chọn action/brightness cuối |
| SafetyDecision | `decision_engine.py` | Hợp đồng kết quả có thể chuyển thành dict/JSON |

Firmware C++ có các file tương ứng trong `src/firmware_esp32/include/lighting_control/` và `src/firmware_esp32/src/lighting_control/`.

## 3. Thứ tự ưu tiên quyết định

1. **Lỗi phần cứng nghiêm trọng** (ví dụ power-stage/relay/overcurrent fault đã được xác định là critical) → `SHUTDOWN`, 0%.
2. **Thermal shutdown hoặc đang chờ hồi phục nhiệt** → `SHUTDOWN`, 0%. Thermal Engine chịu trách nhiệm latch và điều kiện tự hồi phục: nhiệt độ dưới 75°C liên tục 300 giây.
3. Lệnh không hợp lệ/replay → `REJECT`; không thực thi lệnh mới và giữ giá trị logic gần nhất.
4. Không có trạng thái đầu ra lưu hợp lệ sau restart → khởi động ở OFF 0%.
5. Lỗi bus DALI → `HOLD`, không gửi lệnh mới; `physical_output=UNKNOWN`. Giá trị giữ lại chỉ là target logic cuối, không khẳng định ánh sáng vật lý đang ở mức đó.
6. Lỗi RTC → `HOLD` target hợp lệ cuối; không tính lịch bằng thời gian không đáng tin. Các giới hạn an toàn nhiệt vẫn có thể giảm target.
7. Lỗi Fade Controller → `HOLD`, không khởi tạo fade mới.
8. Mất MQTT trên 300 giây → dùng lịch cục bộ nếu RTC và lịch hợp lệ; nếu không có lịch hợp lệ thì HOLD.
9. Lỗi cảm biến ánh sáng → HOLD mức hợp lệ cuối.
10. Lỗi cảm biến nhiệt độ → áp dụng **30% như mức mặc định/tối đa**. Đây không phải lệnh buộc đèn luôn bật: lịch OFF hoặc yêu cầu OFF vẫn đưa target về 0%. Nếu đồng thời có lỗi phần cứng nghiêm trọng, SHUTDOWN 0% có ưu tiên cao hơn.
11. Nhiệt độ trên 75°C đến 90°C → nhân brightness gốc với 0.8. Trên 90°C → SHUTDOWN.

`hardware_faults`/`hardware_critical_fault` chỉ dành cho lỗi phần cứng nghiêm trọng cần cắt đầu ra. Lỗi truyền thông DALI được phân loại riêng: nếu bus đã mất, phần mềm không thể bảo đảm gửi được frame OFF; vì vậy đánh dấu physical output UNKNOWN và HOLD target logic, đồng thời yêu cầu cơ chế ngắt độc lập nếu lỗi vật lý cần shutdown.

## 4. Brightness policy

- Khi online: `base = min(requested_brightness_pct, schedule_brightness_pct)` nếu có giới hạn lịch.
- Khi offline quá 300 giây: dùng `schedule_brightness_pct` từ Offline Fallback Manager.
- Khi lỗi cảm biến nhiệt độ: `base = min(base, 30)`; vì vậy OFF vẫn là OFF.
- Khi thermal derating: `final = base × 0.8` (tính từ base hiện tại, không nhân lặp trên kết quả cũ).
- Luôn clamp kết quả trong [0, 100].
- Không áp dụng nâng mức sáng tối thiểu trong các trạng thái OFF, HOLD hoặc SHUTDOWN.

## 5. API Python

```python
from lighting_control.safety import SafetySupervisor

supervisor = SafetySupervisor(temperature_sensor_fault_brightness_pct=30)
decision = supervisor.evaluate(
    requested_brightness_pct=80,
    schedule_brightness_pct=100,
    temperature_c=30,
    temperature_sensor_valid=True,
    last_valid_brightness_pct=60,
)
print(decision.to_dict())
```

Các đầu vào đáng chú ý:

- `requested_brightness_pct`: target từ nguồn điều khiển đã qua xác thực; có thể `None`.
- `schedule_brightness_pct`: giới hạn lịch; `0` là OFF có chủ đích, `None` là không có dữ liệu lịch ở chu kỳ này.
- `last_valid_brightness_pct`: target logic gần nhất được chấp nhận.
- `hardware_faults`: danh sách mã lỗi phần cứng nghiêm trọng.
- `thermal_shutdown` / `thermal_recovery_pending`: trạng thái latch từ Thermal Engine.
- `module_results`: kết quả `ModuleResult` cần đưa vào danh sách lỗi.

`execution_authorized=True` chỉ có nghĩa quyết định được phép chuyển tới lớp thực thi; không có nghĩa frame đã gửi, driver đã ACK hoặc ánh sáng vật lý đã được xác minh.
