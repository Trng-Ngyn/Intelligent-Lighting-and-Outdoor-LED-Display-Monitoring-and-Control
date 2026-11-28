# S1 — Scaffold firmware ESP32-WROOM-32 (ESP-IDF) và kiểm chứng toolchain

Ngày: 2026-11-27. Phạm vi: **chỉ build cấu hình `esp32_dev`**. Không nạp firmware,
không build/flash profile `secure`, không chạy `espefuse burn`. Không đụng
`src/firmware_esp32/`.

## Toolchain đã cài

| Thành phần | Phiên bản | Kiểm chứng |
| :-- | :-- | :-- |
| PlatformIO Core | 6.2.0 | `python -m platformio --version` |
| Platform | `espressif32@6.11.0` | `platformio.ini` |
| Framework | `platformio/framework-espidf@3.50401.0` | `framework-espidf/package.json` tồn tại |
| ESP-IDF | 5.4.1 | `esp_get_idf_version()` trong scaffold |
| Toolchain | `xtensa-esp32-elf 8.4.0`, `cmake ~3.16`, `ninja 1.9`, `esptool.py 4.5.1` | log build |
| Python IDF | `.platformio/penv/.espidf-5.4.1` | cài `idf-component-manager~=1.5.2`, `esp-idf-kconfig~=2.5.0` |

## Lệnh build

Từ `src/firmware_esp32_idf/`:

```powershell
& '..\..\.venv\Scripts\python.exe' -m platformio run -e esp32_dev
```

Kết quả cuối:

```
RAM:   [          ]   3.4% (used 11128 bytes from 327680 bytes)
Flash: [=         ]  13.0% (used 178392 bytes from 1376256 bytes)
======================== [SUCCESS] Took 300.72 seconds =========================
Environment    Status    Duration
esp32_dev      SUCCESS   00:05:00.716
```

Artifact trong `.pio/build/esp32_dev/`: `firmware.bin` (178.800 bytes),
`firmware.elf`, `bootloader.bin` (25.984 bytes), `partitions.bin` (3.072 bytes),
`ota_data_initial.bin`.

## Các blocker toolchain đã xử lý

| Triệu chứng | Nguyên nhân | Xử lý |
| :-- | :-- | :-- |
| `MissingPackageManifestError: Could not find 'package.json'` | `framework-espidf` bị download dở khi build bị ngắt | Xóa thư mục package, cài lại `framework-espidf@3.50401.0`; kiểm tra `package.json` tồn tại |
| `Error: Missing the 'src' folder with project sources.` | PlatformIO mặc định `src_dir = src`, project ESP-IDF dùng `main/` | Thêm `src_dir = main` trong `[platformio]` |
| `sdkconfig.dev` có `PARTITION_TABLE_SINGLE_APP` dù đã khai `board_build.partitions` | PlatformIO tạo `partitions.bin` từ CSV nhưng không tự bật config custom trong firmware | Thêm `CONFIG_PARTITION_TABLE_CUSTOM=y` và `CONFIG_PARTITION_TABLE_CUSTOM_FILENAME="partitions.csv"` vào `sdkconfig.defaults.common`, xóa `sdkconfig.dev`, build lại |

## Kiểm chứng cấu hình trong `sdkconfig.dev` (đã sinh)

```
CONFIG_IDF_TARGET="esp32"
CONFIG_FREERTOS_HZ=1000
CONFIG_MBEDTLS_TLS_CLIENT=y
CONFIG_MBEDTLS_SSL_PROTO_TLS1_3=y
CONFIG_MQTT_USE_CUSTOM_CONFIG=y
CONFIG_MQTT_TASK_STACK_SIZE=8192
CONFIG_PARTITION_TABLE_CUSTOM=y
CONFIG_PARTITION_TABLE_CUSTOM_FILENAME="partitions.csv"
CONFIG_PARTITION_TABLE_FILENAME="partitions.csv"
# CONFIG_SECURE_FLASH_ENC_ENABLED is not set
# CONFIG_NVS_ENCRYPTION is not set
# CONFIG_SECURE_BOOT is not set
```

Bảng phân vùng parse từ `partitions.bin` bằng `gen_esp32part.py`:

```
nvs,     data, nvs,     0x9000,   24K,
nvs_keys,data, nvs_keys,0xf000,   4K,  encrypted
otadata, data, ota,     0x10000,  8K,
phy_init,data, phy,     0x12000,  4K,
app0,    app,  ota_0,   0x20000,  1344K,
app1,    app,  ota_1,   0x170000, 1344K,
```

## Kiểm chứng API/option trong framework đã cài

- MQTT 5: `components/mqtt/esp-mqtt/include/mqtt5_client.h` có
  `esp_mqtt5_client_set_publish_property` (dòng 184),
  `esp_mqtt5_client_set_user_property` (dòng 247),
  `esp_mqtt5_client_delete_user_property` (dòng 281). Test mẫu
  `test_apps/test_mqtt5/main/test_mqtt5.c` dùng đúng chuỗi 3 bước này.
- `components/mqtt/esp-mqtt/Kconfig` có `MQTT_USE_CUSTOM_CONFIG` (dòng 60) và
  `MQTT_TASK_STACK_SIZE` (dòng 105).
- `components/mbedtls/Kconfig` có `MBEDTLS_SSL_PROTO_TLS1_3` (dòng 176) và
  `MBEDTLS_TLS_CLIENT` (dòng 742).
- `components/bootloader/Kconfig.projbuild` có `SECURE_FLASH_ENC_ENABLED`
  (dòng 879) và `SECURE_FLASH_ENCRYPTION_MODE_DEVELOPMENT` (dòng 939);
  `components/nvs_flash/Kconfig` có `NVS_ENCRYPTION` (dòng 3). Tên config cũ
  `FLASH_ENCRYPTION_ENABLED` / `MBEDTLS_TLS_CLIENT_ENABLE` **không dùng**.
- Binary chứa format string `profile=%s idf=%s` và literal `dev`, không chứa
  `secure` → `build_flags` của env `esp32_dev` đã được áp dụng.

## Ghi chú

- Log build có một cảnh báo Kconfig của IDF về
  `BTDM_CTRL_CONTROLLER_DEBUG_MODE_1` (`visible if` không được hỗ trợ); không
  ảnh hưởng build, không phải lỗi dự án.
- Profile `esp32_secure` chỉ được cấu hình trong `platformio.ini` và
  `sdkconfig.defaults.secure`; **chưa build, chưa flash**. Quy trình re-flash
  dùng `idf.py encrypted-app-flash monitor` với khóa sinh trên chip đã ghi trong
  `README.md`, nhưng chưa thực hiện.
- Không có secret hay nội dung khóa nào được in ra log.
