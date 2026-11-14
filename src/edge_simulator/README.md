# Virtual Edge Simulator (MQTT 5)

Mô phỏng nhiều thiết bị biên (đèn đường, màn hình LED, gateway) kết nối MQTT 5 tới broker,
publish telemetry/status, nhận lệnh dim và phản hồi kết quả. Mỗi thiết bị có một kết nối
MQTT riêng, LWT riêng và khóa HMAC dẫn xuất riêng.

Đặc tả giao thức đầy đủ: [`docs/specifications/MQTT5_COMMUNICATION_PROTOCOL.md`](../../docs/specifications/MQTT5_COMMUNICATION_PROTOCOL.md).

---

## 1. Yêu cầu

- Python 3.11+
- Broker MQTT 5 (Mosquitto 2.x local hoặc `broker.emqx.io:1883` cho dev/test)
- Không cần Docker nếu dùng broker công cộng

Cài đặt:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

---

## 2. Cấu hình

Sao chép file mẫu và đổi khóa:

```powershell
Copy-Item config.example.json config.json
```

Cấu trúc:

```json
{
  "broker": {
    "host": "broker.emqx.io",
    "port": 1883,
    "username": "",
    "password": "",
    "use_tls": false,
    "client_id_prefix": "pcvsim"
  },
  "security": {
    "signing_secret": "dev-only-change-me-please-32chars"
  },
  "simulator": {
    "telemetry_interval_sec": 15,
    "keep_alive_sec": 15,
    "replay_window_ms": 30000,
    "log_level": "INFO",
    "crash_after_sec": null,
    "max_devices": null
  },
  "devices": [
    {
      "site_id": "SITE_01",
      "device_type": "light",
      "device_id_prefix": "LGT_NODE_",
      "count": 50,
      "start_index": 1,
      "index_width": 3,
      "initial_brightness": 50
    },
    {
      "site_id": "SITE_01",
      "device_type": "led_display",
      "device_ids": ["DSP_LED_001"],
      "initial_brightness": 80
    }
  ]
}
```

### Trường quan trọng

| Trường | Ý nghĩa |
| :--- | :--- |
| `security.signing_secret` | Master secret để dẫn xuất khóa HMAC từng thiết bị; tối thiểu 16 ký tự |
| `telemetry_interval_sec` | Chu kỳ publish telemetry |
| `keep_alive_sec` | Keep Alive MQTT; mặc định 15 giây |
| `replay_window_ms` | Cửa sổ chống replay; mặc định 30000 ms |
| `crash_after_sec` | Tự `os._exit()` sau N giây để kiểm thử LWT |
| `max_devices` | Giới hạn số thiết bị sau khi mở rộng |
| `devices[].device_id_prefix` + `count` | Sinh ID hàng loạt, ví dụ `LGT_NODE_001` … `LGT_NODE_050` |
| `devices[].device_ids` | Danh sách ID cố định |

`device_type` chỉ nhận `light`, `led_display`, `gateway`. `site_id`/`device_id` chỉ dùng
`[A-Za-z0-9_-]`, tối đa 64 ký tự.

### Ghi đè bằng biến môi trường

Xem [`.env.example`](../../.env.example). Code đọc trực tiếp biến môi trường, **không tự nạp**
file `.env`:

```powershell
$env:SIM_SIGNING_SECRET = "dev-only-change-me-please-32chars"
$env:SIM_BROKER_HOST = "localhost"
$env:SIM_MAX_DEVICES = "5"
$env:SIM_LOG_LEVEL = "DEBUG"
```

---

## 3. Chạy simulator

```powershell
# Dùng config.json mặc định
.\.venv\Scripts\python.exe src\edge_simulator\virtual_lighting_network.py

# Chỉ định config và giới hạn thiết bị
.\.venv\Scripts\python.exe src\edge_simulator\virtual_lighting_network.py `
  --config config.json --max-devices 5 --log-level INFO

# Tự dừng gracefully sau 20 giây
.\.venv\Scripts\python.exe src\edge_simulator\virtual_lighting_network.py `
  --config tests\fixtures\simulator.test.json --run-seconds 20

# Kiểm thử LWT: thoát không DISCONNECT sau 8 giây
.\.venv\Scripts\python.exe src\edge_simulator\virtual_lighting_network.py `
  --config tests\fixtures\simulator.test.json --crash-after 8
```

> Trên Windows, nếu log tiếng Việt hiển thị sai, đặt `$env:PYTHONUTF8 = "1"` trước khi chạy.
> Simulator cũng tự cấu hình stdout/stderr sang UTF-8.

---

## 4. Kiểm tra nhanh

### Xem status/telemetry/result/alert

```powershell
.\.venv\Scripts\python.exe tools\mqtt5_probe.py --config tests\fixtures\simulator.test.json watch
```

Chỉ theo dõi status để đo LWT:

```powershell
.\.venv\Scripts\python.exe tools\mqtt5_probe.py --config tests\fixtures\simulator.test.json watch --status-only --run-seconds 25
```

### Gửi lệnh dim có ký

```powershell
.\.venv\Scripts\python.exe tools\mqtt5_probe.py --config tests\fixtures\simulator.test.json send-dim --device LGT_NODE_001 --value 65
```

### Chạy Mock Cloud tự gửi lệnh

```powershell
.\.venv\Scripts\python.exe src\backend\mock_cloud_service.py `
  --config tests\fixtures\simulator.test.json `
  --dim-device LGT_NODE_001 --dim-value 65 --send-delay 5 --run-seconds 20
```

Mock Cloud subscribe telemetry/status/alert/result, xác thực chữ ký, log trạng thái và gửi lệnh
dim có ký.

### Dọn retained status

```powershell
.\.venv\Scripts\python.exe tools\mqtt5_probe.py --config tests\fixtures\simulator.test.json clear-status
```

---

## 5. Kiểm thử

```powershell
$env:PYTHONUTF8 = "1"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
.\.venv\Scripts\flake8.exe src\iot_protocol src\edge_simulator src\backend tools\mqtt5_probe.py tests
```

Báo cáo E2E/LWT: [`docs/test_reports/MQTT5_E2E_REPORT.md`](../../docs/test_reports/MQTT5_E2E_REPORT.md).

---

## 6. Broker local bằng Docker

```powershell
docker compose up -d
```

Sau đó đổi `broker.host` thành `localhost` trong `config.json` (hoặc đặt
`$env:SIM_BROKER_HOST = "localhost"`). Cấu hình Mosquitto nằm trong
[`deploy/mosquitto/`](../../deploy/mosquitto/).

Với production, dùng TLS 8883, xác thực theo thiết bị và ACL theo site/type/device; xem
`deploy/mosquitto/mosquitto.secure.conf.example` và `deploy/mosquitto/aclfile.example`.

---

## 7. Hành vi chính

| Tình huống | Hành vi |
| :--- | :--- |
| Kết nối thành công | Publish `status online` retained, subscribe command dim |
| Định kỳ | Publish telemetry QoS 1, retain false |
| Nhận lệnh hợp lệ | Cập nhật brightness/relay, publish result cùng `correlation_id` |
| Lệnh sai chữ ký/replay/hết hạn | Từ chối, publish result/alert tương ứng |
| Dừng graceful | Publish `status offline` retained rồi DISCONNECT |
| Crash/mất điện | Không DISCONNECT; broker phát LWT `offline` retained |

---

## 8. Xử lý sự cố

| Hiện tượng | Nguyên nhân thường gặp | Cách xử lý |
| :--- | :--- | :--- |
| `Không kết nối được broker` | Sai host/port, firewall, broker chưa chạy | Kiểm tra `broker.emqx.io:1883`, chạy `docker compose up -d` |
| `SEC_SIGNATURE_INVALID` | Simulator và Cloud dùng master secret khác nhau | Dùng cùng `config.json` hoặc cùng `SIM_SIGNING_SECRET` |
| `SEC_REPLAY_DETECTED` | Đồng hồ lệch quá 30 giây hoặc gửi lại cùng `correlation_id` | Đồng bộ NTP, không tái sử dụng ID |
| Không thấy offline | Dùng `--run-seconds` (graceful) thay vì `--crash-after` | Dùng `--crash-after` và probe `watch --status-only` |
| Log tiếng Việt lỗi font | Console Windows dùng codepage cũ | Đặt `$env:PYTHONUTF8 = "1"` |
| Retained status cũ | Thiết bị đã bị xóa khỏi config | Chạy `clear-status` |

---

## 9. Bảo mật

- Không commit `config.json` hoặc khóa thật; `.gitignore` đã chặn `config.json`.
- Chỉ dùng `signing_secret` dev/test trong repo.
- Production: TLS, xác thực broker theo thiết bị, ACL tối thiểu, luân chuyển khóa định kỳ.
- HMAC bảo vệ tính toàn vẹn và nguồn gốc, không thay thế mã hóa đường truyền.
