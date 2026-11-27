# S2 — Firmware ESP-IDF: 3 task, mTLS MQTT 5, telemetry Annex C/HMAC

Ngày: 2026-11-27. Phạm vi: **chỉ build/kiểm chứng tĩnh env `esp32_dev`**.
Không nạp firmware, không chạy soak 4h, không build/flash `esp32_secure`,
không `espefuse burn`, không đụng `src/firmware_esp32/`.

## Những gì đã triển khai

| File | Vai trò |
| :-- | :-- |
| `main/main.c` | Khởi tạo NVS, provisioning khi chưa có config, tạo đúng 3 task |
| `main/pccom_config.h` | Kiểu dữ liệu, kích thước, tên namespace NVS, hằng số 10s/15s/QoS1 |
| `main/pccom_nvs.c` | Đọc/ghi cấu hình (PEM, WiFi, secret) và sequence vào NVS |
| `main/pccom_provision.c` | UART1 RX=GPIO16/TX=GPIO17, khung `PCCOM:<base64(TLV)>,<crc32hex>` |
| `main/pccom_security.c` | Dẫn xuất khóa, HMAC-SHA256 canonical `v1`, UUID4, epoch ms, self-test |
| `main/pccom_telemetry.c` | Task nhịp 10s + Ingestion dựng JSON Annex C/ký HMAC |
| `main/pccom_network.c` | WiFi/SNTP/mTLS MQTT 5, LWT, publish duy nhất, mutex publish |
| `main/pccom_reserved.c` | Đặt chỗ namespace lệnh; handler luôn trả `ESP_ERR_NOT_SUPPORTED` |

Luồng dữ liệu: `Telemetry (10s) -> q_sample_req -> Ingestion (JSON + HMAC) ->
q_publish -> Network Manager (publish)`. Không fallback/offline spool: bản tin
bị bỏ khi MQTT chưa kết nối hoặc queue đầy, có log cảnh báo.

`commands/v1/...` và `pccom/v1/...` chỉ là reserved namespace. Không có lệnh
gọi `esp_mqtt_client_subscribe()` trong mã nguồn; không publish `dim/result`.

## Lệnh build và kết quả

Từ `src/firmware_esp32_idf/`, sau khi xóa `sdkconfig.dev` và
`.pio/build/esp32_dev` do đổi `sdkconfig.defaults.common`:

```powershell
& '..\..\.venv\Scripts\python.exe' -m platformio run -e esp32_dev
```

```
RAM:   [=         ]  11.4% (used 37456 bytes from 327680 bytes)
Flash: [=======   ]  72.9% (used 1003248 bytes from 1376256 bytes)
======================== [SUCCESS] Took 15.00 seconds ========================
Environment    Status    Duration
esp32_dev      SUCCESS   00:00:15.000
```

Lần build đầu sau khi thêm mã S2 (full rebuild) cũng SUCCESS, 230.11s.
Artifact: `.pio/build/esp32_dev/firmware.bin`, `firmware.elf`, `bootloader.bin`,
`partitions.bin`, `ota_data_initial.bin`.

## Kiểm chứng cấu hình đã sinh (`sdkconfig.dev`)

```
CONFIG_IDF_TARGET="esp32"
CONFIG_PARTITION_TABLE_CUSTOM=y
CONFIG_PARTITION_TABLE_CUSTOM_FILENAME="partitions.csv"
CONFIG_MQTT_PROTOCOL_5=y
CONFIG_MQTT_USE_CUSTOM_CONFIG=y
CONFIG_MQTT_BUFFER_SIZE=2048
CONFIG_MQTT_TASK_STACK_SIZE=8192
CONFIG_MBEDTLS_TLS_CLIENT=y
CONFIG_MBEDTLS_SSL_PROTO_TLS1_3=y
# CONFIG_SECURE_FLASH_ENC_ENABLED is not set
# CONFIG_SECURE_BOOT is not set
```

`CONFIG_MQTT_PROTOCOL_311` vẫn được IDF bật mặc định song song; firmware ghi đè
bằng `session.protocol_ver = MQTT_PROTOCOL_V_5` lúc chạy, nên kết nối dùng MQTT 5.

## Kiểm chứng biểu tượng (xtensa-esp32-elf-nm trên object của `main/`)

Có định nghĩa `T pccom_network_task`, `T pccom_ingestion_task`,
`T pccom_telemetry_task`, `T pccom_handle_reserved_command`.
Có tham chiếu `U esp_mqtt_client_publish`,
`U esp_mqtt5_client_set_connect_property`,
`U esp_mqtt5_client_set_publish_property`,
`U esp_mqtt5_client_set_user_property`.
**Không có** `esp_mqtt_client_subscribe` trong object của ứng dụng.

## Kiểm chứng HMAC đối chiếu Python

`src/iot_protocol/signing.py` sinh vector công khai (key `0x00..0x1f`, topic
`telemetry/v1/SITE_01/light/LGT_NODE_001`, cid
`00000000-0000-4000-8000-000000000001`, ts `1794660440618`, payload
`pccom-selftest-payload`). Firmware gọi `pccom_security_selftest()` ngay lúc
boot, so sánh chữ ký C với vector Python; nếu sai thì dừng boot và log lỗi.
Đây là kiểm chứng khi chạy trên bo; máy host hiện không có bo/provisioning nên
không tự chạy được self-test này.

## Kiểm chứng binary không chứa credential field

- Có literal `dev` và format string `profile=%s idf=%s`; không có literal
  `secure`.
- Không có hostname broker lab `mqtt.dev.pccom.test` và CN thiết bị
  `dev_SITE_01_LGT_NODE_001` trong firmware.
- Mật khẩu WiFi, PEM và HMAC master secret chỉ được provisioning vào NVS;
  mã nguồn chỉ chứa tên key (`sign_secret`, `ca_pem`, ...), không chứa giá trị.
- Chuỗi `-----BEGIN CERTIFICATE-----` trong binary đến từ bộ parse PEM của
  mbedTLS, không phải cert được nhúng.

## Cảnh báo build

Chỉ có cảnh báo Kconfig của IDF về `BTDM_CTRL_CONTROLLER_DEBUG_MODE_1`
(`visible if` không được hỗ trợ), không phải lỗi dự án.

## Chưa làm (cần bo thật / phê duyệt riêng)

1. Nạp `esp32_dev` lên bo, provisioning qua UART1 bằng CA/cert/key và master
   secret dev, quan sát `+ACK` và log `HMAC self-test OK`.
2. Chạy soak 4h, đối soát payload/schema, QoS/retain/LWT và replay guard với
   broker field `mqtt.dev.pccom.test:8885`.
3. Build/flash `esp32_secure` trên **1 bo dự phòng** chỉ sau phê duyệt riêng;
   khóa sinh trên chip, re-flash bằng `idf.py encrypted-app-flash monitor`,
   không burn `FLASH_CRYPT_CNT`, không chạy `espefuse burn`.
