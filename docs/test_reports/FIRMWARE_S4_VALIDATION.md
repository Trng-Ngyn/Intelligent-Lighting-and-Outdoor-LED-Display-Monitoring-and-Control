# S4 — Tool provisioning UART1 và build kiểm chứng profile `secure`

Ngày: 2026-11-28. Phạm vi: **tool host-side + compile `esp32_secure`**.
Không nạp firmware, không provisioning bo thật, không `espefuse burn`, không
burn `FLASH_CRYPT_CNT`, không dùng file khóa trên host. Không làm test suite.

## Những gì đã triển khai

| File | Vai trò |
| :-- | :-- |
| `tools/provision_esp32.py` | Sinh khung `PCCOM:<base64(TLV)>,<crc32hex>` với TLV version đầu tiên, CRC32-IEEE; ghi ra file hoặc gửi UART1 |
| `.gitignore` | Bỏ qua `*.pccom-frame` vì khung chứa secret ở dạng base64 (decode được) |
| `src/firmware_esp32_idf/README.md` | Hướng dẫn tool, trạng thái build `secure`, cảnh báo không flash |
| `src/firmware_esp32_idf/sdkconfig.defaults.common` | (từ S3) `FLASH_SIZE_4MB` cũng áp dụng cho profile secure |

Tool khớp `main/pccom_provision.c`: tag `0` (version=1, len=1) đứng đầu, sau đó
tag `1..12`, length big-endian 2 byte, CRC32 tính trên **bytes TLV sau decode**.
WiFi password và HMAC master secret chỉ đọc từ `--*-file`, biến môi trường
(`PCCOM_WIFI_PASS`, `PCCOM_SIGNING_SECRET`) hoặc `getpass` ẩn; **không nhận qua
đối số dòng lệnh** để tròn lịch sử shell. Không có chế độ in khung ra stdout:
bắt buộc `--out` hoặc `--port`. Với `--port`, tool đợi `+READY`, gửi khung rồi
in `+ACK` / `-ERR <mã>` (không echo nội dung khung). Chỉ in metadata an toàn:
site/type/device/client/broker, version, số byte và CRC.

## Kiểm chứng tool (credential giả trong temp, ngoài repo)

```text
returncode: 0
-frame-meta site=SITE_01 type=light device=LGT_NODE_001 client=LGT_NODE_001
             broker=mqtt.example.test:8883 version=1 tlv_bytes=331
             frame_bytes=460 crc32=7249888a
VERIFIED: frame_bytes=460 tlv_bytes=331 crc=7249888a tags=[0,1,...,12]
```

- TLV đầu tiên: `tag=0, len=0x0001, value=1` — đúng `PCCOM_PROVISION_VERSION`.
- 13 tag liên tiếp `0..12`, CRC khớp `zlib.crc32`.
- Secret và WiFi password giả **không xuất hiện** trong stdout/stderr của tool.
- Chưa kiểm chứng `--port` trên bo thật (không có bo).

## Lệnh build secure và kết quả

Từ `src/firmware_esp32_idf/`, chưa có `sdkconfig.secure` nên IDF sinh mới từ
`sdkconfig.defaults.common;sdkconfig.defaults.secure`:

```powershell
& '..\..\.venv\Scripts\python.exe' -m platformio run -e esp32_secure
```

```
RAM:   [=         ]  11.5% (used 37548 bytes from 327680 bytes)
Flash: [=======   ]  73.3% (used 1008484 bytes from 1376256 bytes)
======================== [SUCCESS] Took 349.83 seconds ========================
Environment    Status    Duration
esp32_secure   SUCCESS   00:05:49.830
```

Artifact plaintext sinh ra để kiểm chứng compile: `.pio/build/esp32_secure/`
(`firmware.bin`, `firmware.elf`, `bootloader.bin`, `partitions.bin`). **Chưa nạp
lên bo**; khi nạp mới ROM tự mã hóa bằng eFuse key sinh trên chip.

## Kiểm chứng `sdkconfig.secure`

```
CONFIG_SECURE_FLASH_ENC_ENABLED=y
CONFIG_SECURE_FLASH_ENCRYPTION_MODE_DEVELOPMENT=y
CONFIG_FLASH_ENCRYPTION_ENABLED=y
CONFIG_NVS_ENCRYPTION=y
# CONFIG_SECURE_BOOT is not set
CONFIG_ESPTOOLPY_FLASHSIZE="4MB"
CONFIG_MQTT_PROTOCOL_5=y
CONFIG_MBEDTLS_SSL_PROTO_TLS1_3=y
```

Chế độ DEVELOPMENT được giữ để `idf.py encrypted-app-flash monitor` vẫn hoạt
động mà không cần host key. `CONFIG_SECURE_BOOT_V1_SUPPORTED=y` chỉ là năng lực
của SoC, không phải secure boot được bật.

## Kiểm chứng binary

Có literal `secure` (đúng profile) và chuỗi log của IDF về flash encryption
DEVELOPMENT. Không có hostname broker lab `mqtt.dev.pccom.test`, CN
`dev_SITE_01_LGT_NODE_001`, PEM hay secret thực nào. Firmware vẫn chỉ có 3
task ứng dụng và không gọi `esp_mqtt_client_subscribe`.

## Cảnh báo build

Chỉ còn cảnh báo Kconfig của IDF về `BTDM_CTRL_CONTROLLER_DEBUG_MODE_1`
(`visible if` không được hỗ trợ), không phải lỗi dự án.

## Chưa làm (cần bo thật / phê duyệt riêng)

1. Provisioning bo bằng khung tool sinh, quan sát `+ACK`, kiểm tra log
   `HMAC self-test OK` và telemetry phát ra.
2. Soak 4h, log `stats:` mỗi 60s, đối soát payload/schema/QoS/retain/LWT.
3. Flash `esp32_secure` chỉ trên **1 bo dự phòng** sau phê duyệt riêng; re-flash
   bằng `idf.py encrypted-app-flash monitor`, không `espefuse burn`, không burn
   `FLASH_CRYPT_CNT`.
