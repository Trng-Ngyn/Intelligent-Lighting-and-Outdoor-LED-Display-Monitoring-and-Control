# CHANGELOG

## [1.0.0] - 2026-11-14

### Added

- Đặc tả giao thức MQTT 5 đầy đủ tại `docs/specifications/MQTT5_COMMUNICATION_PROTOCOL.md`.
- Package `src/iot_protocol/`:
  - `topics.py`: taxonomy `v1`, kiểm tra segment, wildcard, parse topic.
  - `signing.py`: chuỗi canonical, HMAC-SHA256, dẫn xuất khóa theo thiết bị, ReplayGuard.
  - `headers.py`: User Properties bắt buộc, xác thực envelope, mã alert.
  - `mqtt5.py`: MQTT 5 Properties cho PUBLISH/WILL/CONNECT.
- Virtual Edge Simulator `src/edge_simulator/`:
  - Hỗ trợ nhiều site/thiết bị với một kết nối MQTT 5 riêng cho mỗi thiết bị.
  - Publish telemetry/status, nhận lệnh dim, phản hồi result, phát alert.
  - LWT `offline` retained, Will Delay 0, crash mode `--crash-after`.
  - Cấu hình JSON + ghi đè bằng biến môi trường `SIM_*`.
  - CLI `--config`, `--max-devices`, `--run-seconds`, `--crash-after`, `--log-level`.
- Mock Cloud Service và Core API:
  - Subscribe wildcard telemetry/status/alert/result.
  - Xác thực User Properties, chữ ký và replay.
  - Publish lệnh dim MQTT 5 có ký, `Correlation Data`, `Response Topic`, `Message Expiry`.
- Công cụ `tools/mqtt5_probe.py`:
  - `watch` (kèm `--status-only`), `send-dim`, `clear-status`.
- Hạ tầng và cấu hình:
  - `config.example.json` (50 đèn + 2 LED), `tests/fixtures/simulator.test.json`.
  - `docker-compose.yml`, `deploy/mosquitto/mosquitto.conf`.
  - Mẫu TLS/ACL: `mosquitto.secure.conf.example`, `aclfile.example`.
  - `requirements.txt`, `requirements-dev.txt`, `.env.example`, `.flake8`.
- Kiểm thử:
  - `tests/test_iot_protocol.py`, `tests/test_simulator_config.py` (25 test).
  - Báo cáo E2E/LWT thực tế tại `docs/test_reports/MQTT5_E2E_REPORT.md`.
- Tài liệu:
  - `src/edge_simulator/README.md`.

### Changed

- Topic chuyển sang taxonomy có version `v1` cho telemetry/command/status/alert.
- Payload telemetry/command/result giữ nguyên schema cũ; bổ sung envelope MQTT 5.
- Core API gửi lệnh theo từng thiết bị với khóa dẫn xuất riêng thay vì một khóa dùng chung.
- `Mqtt5Client.publish` hỗ trợ `wait_for_ack` để telemetry/status không chặn luồng mạng.
- Log được cấu hình UTF-8 trên Windows.

### Fixed

- Loại bỏ chờ PUBACK không cần thiết cho telemetry/status/result/alert, giảm độ trễ phản hồi
  lệnh từ khoảng 5 giây xuống dưới 0,3 giây trong môi trường test.
- Alert không còn gắn `Message Expiry Interval` (chỉ lệnh dim mới có expiry 60 giây).
- Loại bỏ import thừa và cấu hình flake8 cho các file có bootstrap `sys.path`.

### Security

- Mọi bản tin bắt buộc `correlation_id`, `ts_ms`, `signature`.
- Chống replay bằng cửa sổ ±30 giây và cache `correlation_id`.
- Khóa HMAC dẫn xuất theo `site/type/device`, không hard-code trong code.
- Status/LWT vẫn xác thực chữ ký nhưng miễn kiểm tra timestamp/replay do Will được ký tại CONNECT.

### Known Limitations

- Firmware ESP32 hiện dùng MQTT 3.1.1 (PubSubClient), chưa hỗ trợ User Properties MQTT 5.
- Chưa kiểm thử với Mosquitto local trong môi trường hiện tại (Docker daemon chưa chạy);
  E2E dùng `broker.emqx.io`.
