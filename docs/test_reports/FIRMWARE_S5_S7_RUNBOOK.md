# S5–S7 — Runbook kiểm chứng firmware trên bo thật

Trạng thái: **chưa thực hiện phần phần cứng**. Máy hiện tại chỉ có `COM3` là
`Intel(R) Active Management Technology - SOL`, không phải ESP32. Không có bo,
không có phê duyệt flash; vì vậy tài liệu này là quy trình để chạy khi có bo,
không phải báo cáo kết quả. Phần host-side đã làm xong và nêu ở cuối.

Nguyên tắc giữ nguyên từ S0–S4:

- Chỉ publish telemetry; **không subscribe** lệnh, không publish `dim/result`,
  không fallback/offline spool.
- Đúng 3 task ứng dụng.
- Không in PEM/private key/WiFi password/HMAC secret ra log hay stdout.
- `esp32_secure` mới chỉ **build** ở S4. Flash secure chỉ sau phê duyệt riêng;
  không `espefuse burn`, không burn `FLASH_CRYPT_CNT`, không bật secure boot.

## Chuẩn bị chung

| Hạng mục | Giá trị/đường dẫn |
| :-- | :-- |
| Bo | ESP32-WROOM-32, flash 4MB (khớp `CONFIG_ESPTOOLPY_FLASHSIZE_4MB`) |
| Cổng | COM thật của USB-UART (thay `COMx` ở mọi lệnh dưới đây) |
| Broker lab | `docker compose --env-file compose.env -f docker-compose.lab.yml up -d --build` |
| Smoke lab | `bash smoke.sh` (phải in `Field 8885: ... checked.` và `ALIGNMENT: PASS`) |
| CA field | `generated\mqtt\field-ca.crt` |
| Cert/key device | `generated\test-clients\dev_SITE_01_LGT_NODE_001.crt` / `.key` |
| Secret | master secret + WiFi pass chỉ đọc từ file ngoài repo, ví dụ `C:\secure\master.secret` và `C:\secure\wifi.pass`; firmware chỉ nhận device key 32 byte |
| Tool | `tools\provision.py` (chính), `tools\provision_esp32.py` (legacy), `tools\verify_firmware_telemetry.py`, `tools\negative_mtls_matrix.py`, `tools\soak_collector.py` |

Chạy mọi lệnh Python từ gốc repo với `& '.\.venv\Scripts\python.exe'`. Chạy
lệnh PlatformIO từ `src\firmware_esp32_idf\` với `& '..\..\.venv\Scripts\python.exe'`.

## S5 — Bring-up dev trên bo

1. Build và nạp profile **dev** (không mã hóa):

   ```powershell
   & '..\..\.venv\Scripts\python.exe' -m platformio run -e esp32_dev
   & '..\..\.venv\Scripts\python.exe' -m platformio run -e esp32_dev -t upload
   & '..\..\.venv\Scripts\python.exe' -m platformio device monitor -e esp32_dev
   ```

   Nếu bo đã có cấu hình cũ, tool sẽ không thấy `+READY`; erase NVS/flash trước
   khi làm tiếp (chỉ trên bo thử nghiệm).

2. Kiểm chứng tiêu cực trước khi ghi NVS. Gửi lần lượt các khung sửa từ khung
   hợp lệ và ghi lại phản hồi:

   | Khung | Phản hồi mong đợi |
   | :-- | :-- |
   | TLV đầu không phải `tag=0 len=1 val=1` | `-ERR BAD_TLV` |
   | CRC chunk/tổng sửa sai | `-ERR CRC_MISMATCH` / `-ERR CRC_MISMATCH_TOTAL` |
   | Base64 hỏng | `-ERR BAD_BASE64` |
   | Chunk sai thứ tự / thiếu chunk | `-ERR BAD_FRAME` |
   | Im lặng 120s | `-ERR TIMEOUT` |

   Đọc lại khung bằng `provision.parse_chunk(bytes)` /
   `provision.parse_chunked(bytes)` trước khi gửi để chắc rằng lỗi nằm ở cấu
   trúc, không phải ở tool.

3. Provision khung thật qua UART1 (RX=GPIO16, TX=GPIO17, 115200 8N1):

   ```powershell
   # Sinh khung chunked vào file ngoài repo
   & '.\.venv\Scripts\python.exe' tools\provision.py build `
       --device-id LGT_NODE_001 --broker-host mqtt.dev.pccom.test `
       --broker-port 8885 --wifi-ssid <SSID> `
       --ca-pem generated\mqtt\field-ca.crt `
       --cert-pem generated\test-clients\dev_SITE_01_LGT_NODE_001.crt `
       --key-pem generated\test-clients\dev_SITE_01_LGT_NODE_001.key `
       --signing-secret-file C:\secure\master.secret `
       --wifi-pass-file C:\secure\wifi.pass `
       --out C:\secure\LGT_NODE_001.chunks

   # Đối chiếu fingerprint (không in PEM/key/secret)
   & '.\.venv\Scripts\python.exe' tools\provision.py show --in C:\secure\LGT_NODE_001.chunks

   # Gửi khung: thay --out bằng --port COMx ở lệnh build, hoặc dùng send
   & '.\.venv\Scripts\python.exe' tools\provision.py send `
       --device-id LGT_NODE_001 --broker-host mqtt.dev.pccom.test `
       --broker-port 8885 --wifi-ssid <SSID> `
       --ca-pem generated\mqtt\field-ca.crt `
       --cert-pem generated\test-clients\dev_SITE_01_LGT_NODE_001.crt `
       --key-pem generated\test-clients\dev_SITE_01_LGT_NODE_001.key `
       --signing-secret-file C:\secure\master.secret `
       --wifi-pass-file C:\secure\wifi.pass `
       --port COMx
   ```

   Mong đợi: `+READY`, từng chunk trả `+OK`, dòng tổng trả `+ACK`; log firmware
   `HMAC self-test OK (vector Python)` và `provisioning thành công; đã lưu vào
   NVS`. `PROV SHOW` ở host và firmware phải cùng `fingerprint` với lúc build
   (đối chiếu bằng device key 32 byte, không in nội dung). Tool chỉ in metadata
   an toàn.

4. Reboot bo **không** provisioning lại: không hiện `+READY`, vẫn kết nối
   mTLS và phát telemetry (chứng tỏ NVS bền vững).

5. Quan sát 10 phút đầu: telemetry mỗi 10s, `status/v1/SITE_01/light/LGT_NODE_001`
   = `online` retained, log `stats:` mỗi 60s. Cắt điện một lần để đo LWT
   `offline` với Will Delay Interval = 0.

6. Ghi `docs/test_reports/FIRMWARE_S5_VALIDATION.md` khi có kết quả thật.

## S6 — Soak 4h và nghiệm thu hợp đồng

1. Giữ nguyên firmware, ghi log monitor vào file **ngoài repo**:

   ```powershell
   & '..\..\.venv\Scripts\python.exe' -m platformio device monitor -e esp32_dev |
       Tee-Object -FilePath 'C:\Users\DELL\AppData\Local\Temp\opencode\firmware_soak.log'
   ```

2. Số liệu mong đợi trong 4h: ~1440 bản tin telemetry (10s), ~240 dòng
   `stats:` (60s). `published` tăng tương ứng; `dropped_samples=0`,
   `dropped_publishes=0` nếu broker khỏe. `publish_failures` / `net_retries`
   nếu khác 0 phải có giải thích trong báo cáo.

3. Kiểm tra không có TWDT panic, không reset, không treo WiFi/SNTP; vẫn đúng
   3 task. So sánh `message_id` với `correlation_id`, `ts_ms` tăng, sequence
   tăng liên tục, QoS 1, telemetry non-retained, status retained.

4. Chạy collector soak 4h (thay vì chỉ verify từng file capture):

   ```powershell
   & '.\.venv\Scripts\python.exe' tools\soak_collector.py `
       --duration-min 240 --secret-file C:\secure\master.secret `
       --out C:\secure\soak_result.json
   ```

   Collector tự kiểm tra jsonschema, `verify_envelope` bằng device key, sequence,
   interval 10s, QoS 1, retain và LWT. Kết quả là file JSON tổng hợp, không chứa
   payload/secret. Kỳ vọng: ≥98% coverage, `error_counts={}`, `status_retained≥1`.

   Với mẫu payload capture riêng lẻ, vẫn có thể dùng:

   ```powershell
   & '.\.venv\Scripts\python.exe' tools\verify_firmware_telemetry.py `
       --payload-file captured.json --props-file props.json `
       --topic telemetry/v1/SITE_01/light/LGT_NODE_001 `
       --site SITE_01 --device-type light --device-id LGT_NODE_001 `
       --secret-file C:\secure\master.secret --last-sequence 6
   ```

   Tool in `OK seq=... message_id=... ts_ms=...`, hoặc từ chối bản tin sửa,
   sai topic, sai `asset_id`, thiếu User Property, sequence hụt/replay.
   Không in secret hay payload.

5. Ma trận mTLS âm đã chạy được trên lab (không cần bo) bằng lệnh dưới đây;
   khi chạy với broker/Staging thật phải lặp lại và đối chiếu mã lỗi:

   ```powershell
   & '.\.venv\Scripts\python.exe' tools\negative_mtls_matrix.py --all
   ```

   Kỳ vọng 8/8: `wrong_ca`, `cert_wrong_ca`, `cn_not_in_acl`, `expired_cert`,
   `missing_client_cert`, `revoked_crl`, `connect_by_ip`, `positive_control`.

6. Ghi `docs/test_reports/FIRMWARE_S6_VALIDATION.md` kèm bảng số liệu
   (mẫu trống: `docs/test_reports/FIRMWARE_S7_SAMPLE_REPORT.md`).

## S7 — Profile `secure` trên 1 bo dự phòng

**Gate:** chỉ thực hiện sau khi có phê duyệt riêng bằng lời/văn bản. Không đụng
đến `FLASH_CRYPT_CNT`, không `espefuse burn`, không bật secure boot, không dùng
host key.

1. `esp32_secure` đã build ở S4. Nếu chưa đổi `sdkconfig.defaults.*` thì dùng
   artifact có sẵn; nếu đổi thì xóa `sdkconfig.secure` và
   `.pio\build\esp32_secure` rồi build lại:

   ```powershell
   & '..\..\.venv\Scripts\python.exe' -m platformio run -e esp32_secure
   ```

2. Nạp bằng luồng IDF native theo README firmware:

   ```bash
   idf.py encrypted-app-flash monitor
   ```

   ROM tự mã hóa bằng eFuse key sinh trên chip. Chế độ DEVELOPMENT vẫn được
   giữ; log `Flash encryption mode is DEVELOPMENT (not secure)` là expected.

3. Provision lại bo dự phòng bằng cert/secret riêng, kiểm tra `+ACK`,
   `HMAC self-test OK`, telemetry hợp lệ. NVS đã mã hóa nhưng vẫn đọc được
   từ firmware.

4. Re-flash một lần để chứng minh không tiêu eFuse; đối chiếu log boot lần 2.

5. Ghi `docs/test_reports/FIRMWARE_S7_VALIDATION.md`, cập nhật README firmware
   từ "đã build, chưa flash" sang "đã flash trên 1 bo dự phòng".

## Phần host-side đã làm xong (không cần bo)

| Việc | Kết quả |
| :-- | :-- |
| `tests/test_firmware_provisioning.py` | legacy: round-trip 13 tag, sai version/CRC/base64, CLI không lộ secret |
| `tests/test_firmware_telemetry.py` | payload hợp lệ, sửa payload, thiếu `correlation_id`, sai `asset_id`, hụt sequence, sai topic |
| `tests/test_firmware_audit.py` | **11 test OK**: device key 32 byte, chunk CRC, `PROV SHOW` không lộ secret, payload qua jsonschema+`verify_envelope`, hợp đồng S3/S5/S7 |
| `tools/provision.py` | host dẫn xuất device key, chunk CRC + tổng CRC, `show` chỉ in fingerprint |
| `tools/verify_firmware_telemetry.py` | kiểm chứng HMAC/schema/topic/sequence với secret đọc từ file/env/prompt ẩn |
| `tools/negative_mtls_matrix.py --all` | lab: **8/8 ca** bị từ chối/kết nối đúng kỳ vọng |
| `tools/soak_collector.py --self-test 5 --interval-sec 1` | 5/5 payload mẫu qua schema+HMAC+sequence; `error_counts={}` (không phải bằng chứng bo) |
| Build sạch `esp32_dev` | `[SUCCESS] Took 321.96 seconds`, RAM 11.5%, Flash 71.5% |
| Build sạch `esp32_secure` (compile only) | `[SUCCESS] Took 319.77 seconds`, RAM 11.5%, Flash 71.8%; **chưa flash** |
| Suite đầy đủ | `python -m unittest discover -s tests -p "test_*.py"` → **114 test OK** |
| CI lint | `flake8 src tools tests lab --select=E9,F63,F7,F82` → **0 lỗi** |
| `git diff --check` | không có whitespace error (chỉ cảnh báo CRLF→LF khi Git chạm file) |

Chạy riêng audit mới:

```powershell
& '.\.venv\Scripts\python.exe' -m unittest tests.test_firmware_audit -v
```
