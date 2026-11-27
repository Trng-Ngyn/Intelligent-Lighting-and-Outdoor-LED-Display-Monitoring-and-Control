# S3 — Hardening firmware ESP-IDF: watchdog, timeout/retry, queue

Ngày: 2026-11-27. Phạm vi: **chỉ build/kiểm chứng tĩnh env `esp32_dev`**.
Không nạp firmware, không chạy soak 4h, không build/flash `esp32_secure`,
không `espefuse burn`, không đụng `src/firmware_esp32/`. Không làm test suite
(theo yêu cầu "việc test chưa gấp").

## Những gì đã triển khai

| File | Vai trò |
| :-- | :-- |
| `main/main.c` | Reconfigure TWDT 30s (`idle_core_mask=0`, `trigger_panic=true`), đăng ký ngay từng task sau khi tạo |
| `main/pccom_config.h` | Hằng S3: WDT 30s, net wait 120s, provisioning idle 120s, version=1; 5 bộ đếm vận hành |
| `main/pccom_telemetry.c` | Feed WDT mỗi vòng, `xQueueReceive` timeout 1s, `q_sample_req` drop-newest, `q_publish` drop-oldest |
| `main/pccom_network.c` | Feed WDT, chờ WiFi+SNTP có timeout 120s, retry WiFi 10s / SNTP 30s, log stats 60s, counters publish/fail/drop |
| `main/pccom_provision.c` | TLV version (tag 0, len 1, val 1) phải đứng đầu; đọc UART timeout 1s, idle timeout 120s → `-ERR TIMEOUT` |
| `sdkconfig.defaults.common` | `CONFIG_ESPTOOLPY_FLASHSIZE_4MB=y` để khớp WROOM-32 và bảng 2 app slot |
| `README.md` | Mô tả frame version, timeout và chính sách queue |

Các task fatal path đều gọi `esp_task_wdt_delete(NULL)` trước `vTaskDelete(NULL)`
để không để entry của task đã chết trong TWDT. Vẫn đúng 3 task ứng dụng; MQTT
client của IDF chỉ tạo task nội bộ của nó. Không subscribe lệnh, không publish
kết quả, không fallback offline.

## Lệnh build và kết quả

Từ `src/firmware_esp32_idf/`:

```powershell
& '..\..\.venv\Scripts\python.exe' -m platformio run -e esp32_dev
```

Lần build tăng tốc sau khi sửa code S3 (chưa đổi defaults):

```
RAM:   [=         ]  11.4% (used 37472 bytes from 327680 bytes)
Flash: [=======   ]  73.1% (used 1005608 bytes from 1376256 bytes)
========================= [SUCCESS] Took 15.02 seconds =========================
```

Sau khi thêm `CONFIG_ESPTOOLPY_FLASHSIZE_4MB=y` vào defaults, xóa
`sdkconfig.dev` và `.pio/build/esp32_dev` rồi full rebuild:

```
RAM:   [=         ]  11.4% (used 37472 bytes from 327680 bytes)
Flash: [=======   ]  73.1% (used 1005608 bytes from 1376256 bytes)
======================== [SUCCESS] Took 266.63 seconds ========================
Environment    Status    Duration
esp32_dev      SUCCESS   00:04:26.634
```

Artifact: `.pio/build/esp32_dev/firmware.bin`, `firmware.elf`,
`bootloader.bin`, `partitions.bin`, `ota_data_initial.bin`.

## Kiểm chứng cấu hình đã sinh (`sdkconfig.dev`)

```
CONFIG_ESPTOOLPY_FLASHSIZE="4MB"
CONFIG_PARTITION_TABLE_CUSTOM=y
CONFIG_PARTITION_TABLE_CUSTOM_FILENAME="partitions.csv"
CONFIG_MQTT_PROTOCOL_5=y
CONFIG_MBEDTLS_SSL_PROTO_TLS1_3=y
# CONFIG_SECURE_FLASH_ENC_ENABLED is not set
CONFIG_ESP_TASK_WDT_TIMEOUT_S=5
```

`CONFIG_ESP_TASK_WDT_TIMEOUT_S=5` là giá trị sdkconfig lúc boot; `app_main` gọi
`esp_task_wdt_reconfigure()` sang 30s trước khi tạo task, nên runtime dùng 30s.
Cảnh báo "Flash memory size mismatch: expected 4MB, found 2MB" của S2 đã hết;
lệnh đóng image giờ dùng `--flash_size 4MB`, khớp `app1` kết thúc ở `0x2C0000`.

## Kiểm chứng biểu tượng (`xtensa-esp-elf-nm` trên `firmware.elf`)

Có: `T esp_task_wdt_reconfigure`, `T esp_task_wdt_add`, `T esp_task_wdt_reset`,
`T esp_task_wdt_delete`, `T esp_sntp_stop`, `T pccom_network_task`,
`T pccom_ingestion_task`, `T pccom_telemetry_task`.

**Không có** `esp_mqtt_client_subscribe` trong firmware (W5 vẫn chưa bật nhánh
lệnh).

## Kiểm chứng binary

Có literal `-ERR TIMEOUT`, `BAD_TLV`, `PCCOM:` và chuỗi log drop-oldest.
Không có hostname broker lab `mqtt.dev.pccom.test`, CN
`dev_SITE_01_LGT_NODE_001` hay bất kỳ credential field nào. Secret/PEM/WiFi
password chỉ nhập qua UART và lưu NVS.

## Cảnh báo build

Chỉ còn cảnh báo Kconfig của IDF về `BTDM_CTRL_CONTROLLER_DEBUG_MODE_1`
(`visible if` không được hỗ trợ), không phải lỗi dự án.

## Chưa làm (cần bo thật / phê duyệt riêng)

1. Nạp `esp32_dev` lên bo, provisioning khung có TLV version, quan sát `+ACK`,
   thử khung thiếu version → `-ERR BAD_TLV` và thử im lặng 120s → `-ERR TIMEOUT`.
2. Chạy soak 4h, quan sát log `stats:` mỗi 60s và kiểm tra không có TWDT panic.
3. Build/flash `esp32_secure` trên **1 bo dự phòng** chỉ sau phê duyệt riêng;
   khóa sinh trên chip, re-flash bằng `idf.py encrypted-app-flash monitor`,
   không burn `FLASH_CRYPT_CNT`, không chạy `espefuse burn`.
