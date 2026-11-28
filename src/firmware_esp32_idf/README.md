# Firmware ESP32-WROOM-32 (ESP-IDF)

Project thay thế dần `src/firmware_esp32/` (Arduino). Hiện mới ở mốc **S1:**
scaffold + kiểm chứng toolchain. Chưa có telemetry/MQTT/HMAC/3 task (S2).
Bằng chứng build: `docs/test_reports/FIRMWARE_S1_VALIDATION.md`.

## Toolchain

- PlatformIO Core 6.2+, `platform = espressif32@6.11.0`, framework
  `platformio/framework-espidf@3.50401.0` = ESP-IDF **5.4.1**.
- `src_dir = main` vì project ESP-IDF dùng `main/`, không phải `src/` mặc định.
- Chạy từ thư mục này (venv nằm ở gốc repo):

```powershell
& '..\..\.venv\Scripts\python.exe' -m platformio run -e esp32_dev
& '..\..\.venv\Scripts\python.exe' -m platformio device monitor -e esp32_dev
```

## Hai profile sdkconfig

`platformio.ini` khai báo rõ từng env:

| Env | sdkconfig | SDKCONFIG_DEFAULTS | Flash encryption |
| :-- | :-- | :-- | :-- |
| `esp32_dev` | `sdkconfig.dev` | `sdkconfig.defaults.common;sdkconfig.defaults.dev` | OFF |
| `esp32_secure` | `sdkconfig.secure` | `sdkconfig.defaults.common;sdkconfig.defaults.secure` | ON + NVS encryption |

**Khi đổi profile hoặc sửa `sdkconfig.defaults.*`, phải xóa `sdkconfig.dev` /
`sdkconfig.secure` (và thư mục build của env tương ứng) rồi build lại.**
Nếu không, file sdkconfig đã sinh sẽ đè các giá trị defaults.

profile `esp32_secure` chỉ dành cho 1 bo dự phòng ở S2, **không được flash khi
chưa có phê duyệt riêng**. Không chạy `espefuse burn`, không burn `FLASH_CRYPT_CNT`.

## Nạp lại sau khi bật flash encryption

Khóa flash encryption được **sinh trên chip**, không lưu trên host. Vì vậy không
dùng luồng `board_build.encryption_key` + `pio run -t encrypt` (cần host key).
Khi cần nạp app đã mã hóa, dùng trực tiếp IDF native:

```bash
idf.py encrypted-app-flash monitor
```

ROM download mode tự dùng eFuse key để mã hóa dữ liệu nạp; lệnh này **không**
tiêu bit `FLASH_CRYPT_CNT`. "3 lần" là số lần **tắt** flash encryption, không
phải số lần re-flash.

## Partition

`partitions.csv`: `app0` ở `0x20000` (0x150000), `app1` ở `0x170000` (0x150000),
không cần `spiffs`; `nvs_keys` giữ flag `encrypted`.

PlatformIO tạo `partitions.bin` trực tiếp từ CSV, nhưng firmware vẫn cần
`CONFIG_PARTITION_TABLE_CUSTOM=y` và
`CONFIG_PARTITION_TABLE_CUSTOM_FILENAME="partitions.csv"` (đã khai báo trong
`sdkconfig.defaults.common`) để config trong firmware khớp bảng nạp.
