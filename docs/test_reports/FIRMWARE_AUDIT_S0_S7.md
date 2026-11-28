# Audit W5-IoT firmware S0→S7 — trạng thái hiện tại

Ngày audit: 2026-11-28. Phạm vi: bằng chứng lệnh/output thật trên host + lab,
không có bo ESP32 thật. **Không commit, không push** theo yêu cầu mới nhất.

Ký hiệu trạng thái:

- `PASS` — có lệnh đã chạy và output tương ứng ở dưới.
- `FAIL (đã sửa, có bằng chứng)` — từng fail/RED trong audit này, đã sửa và có
  output xanh sau sửa.
- `CẦN BO` — thiết kế/tool/build xong nhưng bắt buộc phần cứng hoặc phê duyệt
  riêng; **không đánh dấu pass**.
- `CHƯA LÀM` — chưa có mã/bằng chứng.

## Bảng S0–S7

| Stage | Trạng thái | Bằng chứng rút gọn |
| :-- | :-- | :-- |
| **S0** — khử blocker lab | `PASS` | `docker compose ... up -d --build`, `bash smoke.sh` → `Field 8885: per-device cert...`, `ALIGNMENT: PASS`; TLS 1.3 `Verification: OK`; ACL publish `PUBACK RC:16`, sai cert `tlsv1 alert unknown ca` (xem `LAB_S0_VALIDATION.md`) |
| **S1** — scaffold/toolchain | `PASS` | `platform = espressif32@6.11.0` (IDF 5.4.1), build sạch `esp32_dev` `[SUCCESS] Took 321.96 seconds` |
| **S2** — 3 task, mTLS, telemetry | `PASS` (host/code/build) · `CẦN BO` (runtime) | `nm firmware.elf` có `pccom_network_task`, `pccom_ingestion_task`, `pccom_telemetry_task`, `pccom_copy_device_key`; **không** có `esp_mqtt_client_subscribe`, **không** có `pccom_derive_device_key`, binary không có literal `dim/result`; 5/5 payload mẫu qua `jsonschema` + `verify_envelope` |
| **S3** — watchdog/timeout/retry/queue | `PASS` (static/build) · `CẦN BO` (runtime) | 11 test audit OK gồm WDT 30s > net attempt 25s, backoff 1→30s+jitter, CN verify, stats 60s; build dev SUCCESS. Hành vi TWDT/queue trên bo: `CẦN BO` |
| **S4** — provisioning + secure compile | `PASS` (host/compile) · `CẦN BO` (UART thật) | `tools/provision.py` dẫn xuất device key 32 byte trên host, chunk CRC + tổng CRC, `show` không lộ secret; build sạch `esp32_secure` `[SUCCESS] Took 319.77 seconds`; chưa nạp bo |
| **S5** — bring-up dev trên bo | `CẦN BO` | COM3 là `Intel(R) Active Management Technology - SOL`, không phải ESP32. Chưa flash, chưa provisioning, chưa đọc log boot |
| **S6** — soak 4h + ma trận âm | `PASS` (ma trận lab + collector self-test) · `CẦN BO` (soak bo) | `tools/negative_mtls_matrix.py --all` → **8/8**; `tools/soak_collector.py --self-test 5 --interval-sec 1` → `schema_ok=5, signature_ok=5, sequence_ok=5, error_counts={}` (dữ liệu mẫu, không phải bo). Soak 1440 bản tin/4h: `CẦN BO` |
| **S7** — profile `secure` trên 1 bo dự phòng | `CẦN BO` + gate phê duyệt | Chỉ compile SUCCESS; config `CONFIG_SECURE_FLASH_ENC_ENABLED=y`, `CONFIG_NVS_ENCRYPTION=y`, `CONFIG_SECURE_BOOT` **không** bật. Không `espefuse burn`, không flash, không burn `FLASH_CRYPT_CNT` |

Tổng: S0, S1 `PASS`; S2–S4 `PASS` ở phần host/lab nhưng còn `CẦN BO` runtime;
S5 `CẦN BO`; S6 `PASS` ma trận/host, `CẦN BO` soak; S7 `CẦN BO` + phê duyệt.
**Không có hạng mục nào được đánh dấu pass khi thiếu bo/broker thật.**

## Các fail đã sửa trong audit này

| Lúc đầu | Triệu chứng | Sau sửa (bằng chứng) |
| :-- | :-- | :-- |
| `tests/test_firmware_audit.py` (TDD RED) | 11 test → `FAILED (failures=3, errors=8)` | `Ran 11 tests ... OK` |
| `test_s3_network_contract_present` | fail do literal `skip_cert_common_name_check` nằm trong comment | Đổi comment thành "không tắt kiểm tra hostname/CN"; test `... ok` |
| `test_s6_negative_matrix_script_lists_all_cases` | error do thiếu `tools/negative_mtls_matrix.py` | Tạo tool; `--all` → `TỔNG: 8/8 ca đúng kỳ vọng` |
| Compile firmware | `comma + 1 == NULL [-Werror=address]`, `.task.task_name` không tồn tại trong esp-mqtt IDF 5.4 | Build dev SUCCESS; dùng `xTaskGetHandle("mqtt_task")` |
| `tests/test_firmware_audit` payload | `SystemExit: 2` do tool chỉ nhận subcommand; `verify_envelope` nhận dict thay vì bytes | Tool nhận cả cú pháp flat, test truyền JSON text; 6/6 OK |
| Ma trận mTLS | `wrong_ca` dùng field CA làm CA sai nhưng server cert do **server CA** ký → ca này `exit=0` | Đổi `SERVER_CA`/`WRONG_CA`; `certificate verify failed` xuất hiện |
| Collector self-test | collector và publisher cùng CN `bridge-s01` → broker đóng kết nối cũ | Publisher dùng cert device; `telemetry_received=5, error_counts={}` |

## Lệnh/output đã chạy (tóm tắt)

```text
python -m unittest tests.test_firmware_audit -v
  Ran 11 tests in 1.765s — OK

python -m unittest discover -s tests -p "test_*.py"
  Ran 114 tests in 3.493s — OK

python -m flake8 src tools tests lab --select=E9,F63,F7,F82
  (không có output) — 0 lỗi

git diff --check
  (chỉ warning LF will be replaced by CRLF; không có whitespace error)

pio run -e esp32_dev     (sau khi xoá .pio/build/esp32_dev + sdkconfig.dev)
  RAM 11.5% (37536/327680), Flash 71.5% (984624/1376256)
  [SUCCESS] Took 321.96 seconds

pio run -e esp32_secure   (sau khi xoá .pio/build/esp32_secure + sdkconfig.secure)
  RAM 11.5% (37612/327680), Flash 71.8% (987584/1376256)
  [SUCCESS] Took 319.77 seconds   <-- compile only, KHÔNG flash

xtensa-esp32-elf-nm firmware.elf | Select-String ...
  400d3e00 T pccom_copy_device_key
  400d42bc T pccom_ingestion_task
  400d4e10 T pccom_network_task
  400d4228 T pccom_telemetry_task
  400d77dc T esp_mqtt_client_publish
  (không có esp_mqtt_client_subscribe, không có pccom_derive_device_key)

python -c "... firmware.bin ..."
  dim/result literal: False
  sign_secret marker: False
  device_key key: True

python tools/negative_mtls_matrix.py --all
  PASS wrong_ca             certificate verify failed
  PASS cert_wrong_ca        tlsv1 alert unknown ca
  PASS cn_not_in_acl        PUBACK RC:135; Not authorized
  PASS expired_cert         tlsv1 alert certificate expired
  PASS missing_client_cert  tlsv13 alert certificate required
  PASS revoked_crl          tlsv1 alert certificate revoked
  PASS connect_by_ip        verify error:num=62:hostname mismatch
  PASS positive_control     CONNACK (0); PUBACK RC:16
  TỔNG: 8/8 ca đúng kỳ vọng

python tools/soak_collector.py --self-test 5 --interval-sec 1 --out <temp>.json
  telemetry_received=5, schema_ok=5, signature_ok=5, sequence_ok=5,
  qos1_ok=5, telemetry_non_retained=5, interval_ok=4, status_retained=1,
  error_counts={}, self_test=true
```

## Danh sách `CẦN BO` theo thứ tự

Chạy từ gốc repo; Python luôn dùng `& '.\.venv\Scripts\python.exe'`, PlatformIO
dùng `& '..\..\.venv\Scripts\python.exe'` từ `src\firmware_esp32_idf\`. Thay
`COMx` bằng cổng USB-UART thật.

1. **Flash profile dev (không mã hóa).**
   ```powershell
   & '..\..\.venv\Scripts\python.exe' -m platformio run -e esp32_dev -t upload
   & '..\..\.venv\Scripts\python.exe' -m platformio device monitor -e esp32_dev
   ```
   Kỳ vọng: boot log `PCCOM ESP32-WROOM-32 firmware ready`, `HMAC self-test OK
   (vector Python)`, `+READY` (NVS trống). Không đụng eFuse/secure profile.

2. **Provisioning device key + đối chiếu fingerprint.**
   ```powershell
   & '.\.venv\Scripts\python.exe' tools\provision.py build --device-id LGT_NODE_001 `
     --broker-host mqtt.dev.pccom.test --broker-port 8885 --wifi-ssid <SSID> `
     --ca-pem generated\mqtt\field-ca.crt `
     --cert-pem generated\test-clients\dev_SITE_01_LGT_NODE_001.crt `
     --key-pem generated\test-clients\dev_SITE_01_LGT_NODE_001.key `
     --signing-secret-file C:\secure\master.secret `
     --wifi-pass-file C:\secure\wifi.pass --out C:\secure\LGT_NODE_001.chunks
   & '.\.venv\Scripts\python.exe' tools\provision.py show --in C:\secure\LGT_NODE_001.chunks
   # gửi: thêm --port COMx (hoặc dùng subcommand send)
   ```
   Kỳ vọng: mỗi chunk trả `+OK`, dòng tổng trả `+ACK`; `fingerprint` của `show`
   khớp lúc build; `device_key_len=32`; log firmware `provisioning thành công;
   đã lưu vào NVS`. Không in PEM/key/secret. Reboot lần 2 không hiện `+READY`.

3. **WiFi + SNTP lấy epoch thật.**
   ```powershell
   & '..\..\.venv\Scripts\python.exe' -m platformio device monitor -e esp32_dev
   ```
   Kỳ vọng: `WiFi STA đã có IP`, `đồng bộ thời gian SNTP thành công`, rồi mới
   `MQTT 5 đã kết nối`; `ts_ms`/`source_time` trong payload là epoch hiện tại
   (không phải 0/mốc boot).

4. **mTLS lab 8885 trên firmware.**
   ```powershell
   docker compose --env-file compose.env -f docker-compose.lab.yml ps
   ```
   Kỳ vọng: TLS 1.3, verify CN `mqtt.dev.pccom.test` (kể cả khi broker gọi bằng
   IP), `CONNACK 0`; log không có `skip...CN`; sai cert thì dừng retry sau 3 lỗi.

5. **Telemetry 10s + status retained/LWT.**
   ```powershell
   & '.\.venv\Scripts\python.exe' tools\soak_collector.py --duration-min 10 `
     --secret-file C:\secure\master.secret --out C:\secure\soak_10min.json
   ```
   Kỳ vọng: ~60 bản tin/10 phút, `sequence_ok` liên tục, QoS 1, telemetry
   non-retained, `status/v1/SITE_01/light/LGT_NODE_001` retained `online`.
   Cắt điện một lần: `offline` xuất hiện ≤30s kể từ bản tin cuối, Will Delay 0.

6. **Heap/stack 10–15 phút.**
   ```powershell
   & '..\..\.venv\Scripts\python.exe' -m platformio device monitor -e esp32_dev |
       Tee-Object -FilePath 'C:\Users\DELL\AppData\Local\Temp\opencode\firmware_heap.log'
   ```
   Kỳ vọng: dòng `stats:` mỗi 60s có `free_heap`, `min_free_heap`,
   `largest_block`, `reconnect`, `publish_fail`, `queue_overflow`, `stack_min`
   cho 4 task (net/ingest/tele/mqtt); không TWDT panic, không reboot, heap không
   suy về 0.

7. **Lặp ma trận mTLS/LWT với broker thật.**
   ```powershell
   & '.\.venv\Scripts\python.exe' tools\negative_mtls_matrix.py --all
   ```
   Kỳ vọng: 8/8 như phần output ở trên (nếu Staging khác lab, cập nhật CA/CN
   trong command fixture trước khi chạy).

8. **Soak 4h + điền báo cáo đo được.**
   ```powershell
   & '.\.venv\Scripts\python.exe' tools\soak_collector.py --duration-min 240 `
     --secret-file C:\secure\master.secret --out C:\secure\soak_result.json
   ```
   Kỳ vọng: ≈1440 bản tin, coverage ≥98%, `error_counts={}`; điền
   `docs/test_reports/FIRMWARE_S7_SAMPLE_REPORT.md` bằng số thật rồi đổi tên
   thành báo cáo đo được. Self-test host-side **không** được chép vào đây.

9. **Profile `secure` trên 1 bo dự phòng — chỉ sau phê duyệt riêng.**
   ```powershell
   # gate: có phê duyệt bằng lời/văn bản
   idf.py encrypted-app-flash monitor
   ```
   Kỳ vọng: ROM dùng eFuse key sinh trên chip, log `Flash encryption mode is
   DEVELOPMENT (not secure)`; re-flash một lần không tiêu `FLASH_CRYPT_CNT`.
   **Cấm** `espefuse burn`, cấm host key, cấm bật secure boot trong đợt này.

## Rủi ro / phụ thuộc Staging

1. **HMAC Staging chưa xác nhận.** Chưa rõ Staging verify bằng master secret hay
   device key riêng từng thiết bị. Thiết kế hiện tại chỉ gửi device key 32 byte
   cho firmware; nếu Staging kỳ vọng master secret thì phải có quyết định đổi
   thiết kế/ủy quyền trước khi integration. `CẦN XÁC NHẬN Staging`.
2. **CA/CN khác lab.** Server cert lab do server CA ký và có SAN
   `mqtt.dev.pccom.test`, `localhost`, `127.0.0.1`; client cert field do field CA
   ký. Staging phải cung cấp CA server, CN/SAN và CA client tương ứng; nếu gọi
   bằng IP thì cập nhật `PCCOM_CERT_COMMON_NAME`, **không tắt verify CN**.
3. **Retain/LWT policy.** Lab dùng plugin `pccom-retain.so` ép telemetry
   non-retained và status retained. Staging cần policy tương đương, nếu không
   LWT `offline` có thể bị ghi đè hoặc QoS/retain lệch hợp đồng.
4. **Hạn cert lab.** Các cert test hết hạn `2026-12-04`; nếu chạy soak sau mốc
   này phải `bash generate-pki.sh` lại và provision lại bo.
5. **Flash encryption.** NVS key sinh trên chip; bo secure phải provision riêng
   bằng cert/device key riêng. Không chia sẻ device key giữa các bo.
6. **Không có bo thật.** `COM3` là Intel AMT SOL, mọi mục S5–S7 runtime vì thế
   vẫn `CẦN BO`. Không flash/provision/soak được trong môi trường hiện tại.
7. **Secret hygiene.** Master secret chỉ nằm ở file/env trên host; không in ra
   log, không commit. File khung chunked chứa device key ở dạng base64 — luôn
   đặt ngoài repo.

## Ghi chú repo

Working tree có các thay đổi chưa commit (firmware, tool, test, runbook, báo cáo).
Theo yêu cầu mới nhất: **không commit, không push**. Không có cert/key/secret,
`sdkconfig.*`, `.pio/`, `generated/` nào được đưa vào báo cáo hay diff.
