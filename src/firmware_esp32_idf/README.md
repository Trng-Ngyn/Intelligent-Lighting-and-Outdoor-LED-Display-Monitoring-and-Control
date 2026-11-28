# Firmware ESP32-WROOM-32 (ESP-IDF)

Project thay thế dần `src/firmware_esp32/` (Arduino). Đã sang mốc **S2+S3+S4:**
telemetry Annex C, HMAC-SHA256, mTLS MQTT 5, đúng 3 task FreeRTOS, hardening
(watchdog, timeout/retry, chính sách queue), tool provisioning và build profile
`secure`. Bằng chứng: `docs/test_reports/FIRMWARE_S1_VALIDATION.md`,
`FIRMWARE_S2_VALIDATION.md`, `FIRMWARE_S3_VALIDATION.md`,
`FIRMWARE_S4_VALIDATION.md`.

**S2/S3/S4 mới chỉ dừng ở mức build/kiểm chứng tĩnh.** Chưa nạp firmware, chưa
chạy soak 4h trên bo thật. `esp32_secure` đã **build để kiểm chứng compile**,
chưa flash, không `espefuse burn`, không burn `FLASH_CRYPT_CNT`.

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

profile `esp32_secure` chỉ dành cho 1 bo dự phòng. Đã build ở S4 để kiểm chứng
compile; **vẫn không được flash khi chưa có phê duyệt riêng**. Không chạy
`espefuse burn`, không burn `FLASH_CRYPT_CNT`.

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

## Kiến trúc S2 (3 task ứng dụng)

| Task | Nhịp | Việc làm |
| :-- | :-- | :-- |
| `pccom-net` | sự kiện + 1s poll queue | WiFi STA, SNTP, mTLS MQTT 5, giữ LWT, **duy nhất** nơi gọi publish |
| `pccom-ingest` | theo `q_sample_req` | Dựng payload Annex C, lấy sequence từ NVS, ký HMAC, đẩy vào `q_publish` |
| `pccom-tele` | `vTaskDelayUntil` 10s | Chỉ gửi yêu cầu lấy mẫu vào `q_sample_req` |

Không có task thứ tư. MQTT client của ESP-IDF tự tạo task nội bộ của nó.

### Hardening S3

- **TWDT:** cấu hình lại từ 5s (mặc định sdkconfig, có giám sát idle task) sang
  **30s**, `idle_core_mask=0`, `trigger_panic=true`. Cả 3 task được đăng ký và
  feed ở đầu mỗi vòng lặp; task thoát lỗi sẽ tự hủy đăng ký để không để entry
  "task đã chết" trong TWDT.
- **Thời gian/chờ mạng:** Network Manager chờ WiFi+SNTP tối đa **120s**, poll
  1s. Sau 10s chưa có IP gọi lại `esp_wifi_connect()`; sau 30s chưa sync gọi
  `esp_sntp_stop()` → `esp_sntp_init()` lại. Quá timeout thì task dừng có kiểm
  soát (không treo vĩnh viễn). Log thống kê mỗi **60s**.
- **Provisioning:** đọc UART với timeout 1s/lần và **idle timeout 120s**;
  hết thời gian trả `-ERR TIMEOUT` rồi `app_main` thử lại sau 3s.
- **Chính sách queue:**
  - `q_sample_req` (len 4): đầy thì **bỏ nhịp mới nhất**, không block nhịp 10s.
  - `q_publish` (len 8): đầy thì **drop-oldest**, giữ bản tin mới nhất.
  - MQTT chưa nối: bỏ bản tin khi lấy ra, **không đệm offline**.
  - Bộ đếm `dropped_samples`, `dropped_publishes`, `published`,
    `publish_failures`, `net_retries` chỉ để log, không đổi logic nghiệp vụ.

Phạm vi bản tin:

- Publish `telemetry/v1/{site}/{type}/{id}`, QoS 1, retain false,
  Content-Type `application/json`.
- Publish `status/v1/{site}/{type}/{id}` = `online` lúc CONNECT và
  `offline` qua LWT, QoS 1, retain true, Will Delay Interval = 0, keepalive 15s.
- Mọi bản tin có User Properties `correlation_id`, `ts_ms`, `signature`;
  canonical `v1\n{topic}\n{cid}\n{ts_ms}\n{payload}`; khóa
  `HMAC-SHA256(master_secret, "{site}/{type}/{id}")`.
- **Không subscribe** `commands/v1/...`, không publish `dim/result`, không
  fallback offline. Topic/handler lệnh chỉ đặt chỗ trong `pccom_reserved.*`.

## Provisioning UART1 (lần đầu boot)

Nếu NVS chưa có cấu hình, `app_main` chặn và chờ khung trên UART1
(RX=GPIO16, TX=GPIO17, 115200 8N1):

```text
PCCOM:<base64(TLV)>,<crc32hex>\n
TLV = tag(1 byte) | length(2 byte big-endian) | value
```

TLV đầu tiên **bắt buộc** là version: `tag=0, length=1, value=0x01`. Khung
thiếu/sai version bị từ chối (`-ERR BAD_TLV`) trước khi ghi NVS.

CRC32-IEEE (poly `0xEDB88320`) tính trên **bytes TLV sau khi decode**, ghi
thành 8 chữ số hex. Firmware trả `+READY`, `+ACK` hoặc `-ERR <mã>`; **không
echo nội dung khung**, không log mật khẩu/PEM/secret.

| Tag | Trường | Bắt buộc |
| :-- | :-- | :-- |
| 0 | `version` = 1 (1 byte, phải đứng đầu) | có |
| 1 | `site_id` | có |
| 2 | `device_type` (`light`/`led_display`/`gateway`) | có |
| 3 | `device_id` | có |
| 4 | `broker_host` | có |
| 5 | `broker_port` (2 byte big-endian) | có |
| 6 | CA PEM của broker | có |
| 7 | client certificate PEM | có |
| 8 | client private key PEM | có |
| 9 | HMAC master secret | có |
| 10 | WiFi SSID | có |
| 11 | WiFi password | có |
| 12 | MQTT client id / username (CN cert) | có |

Các giá trị được lưu vào namespace NVS `pccom_cfg`; sequence nằm ở
`pccom_rt`. Với profile `secure`, NVS được mã hóa và khóa sinh trên chip.

### Tool sinh khung (S4)

Dùng `tools/provision_esp32.py` từ gốc repo. Tool bắt đầu bằng TLV version,
tính CRC32-IEEE và **không in khung ra màn hình** (base64 không phải mã hóa);
bắt buộc `--out <file>` hoặc `--port <serial>`:

```powershell
& '.\.venv\Scripts\python.exe' tools\provision_esp32.py `
    --device-id LGT_NODE_001 --broker-host mqtt.example.test `
    --broker-port 8883 --wifi-ssid LAB_WIFI `
    --ca-pem generated\mqtt\field-ca.crt `
    --cert-pem generated\test-clients\dev_SITE_01_LGT_NODE_001.crt `
    --key-pem generated\test-clients\dev_SITE_01_LGT_NODE_001.key `
    --signing-secret-file C:\secure\master.secret `
    --wifi-pass-file C:\secure\wifi.pass `
    --out C:\Users\DELL\AppData\Local\Temp\opencode\LGT_NODE_001.pccom-frame
```

Thay `--out` bằng `--port COM3` để đợi `+READY` rồi gửi khung và in phản hồi
`+ACK` / `-ERR <mã>`. WiFi password và master secret đọc từ file, biến môi
trường (`PCCOM_WIFI_PASS`, `PCCOM_SIGNING_SECRET`) hoặc prompt ẩn — không nhận
qua đối số dòng lệnh. File khung có đuôi `*.pccom-frame` đã nằm trong
`.gitignore`.

Khi cần thay broker/dev/profile, phải xóa `sdkconfig.dev` / `sdkconfig.secure`
và build lại env tương ứng như mô tả ở phần trên.
