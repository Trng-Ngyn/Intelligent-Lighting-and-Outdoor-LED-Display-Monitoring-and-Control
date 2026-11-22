# CHANGELOG

## [1.1.0] - 2026-11-16

### Added

- Quyết định Phương án C và traceability RFP tại `docs/proposals/TOPIC_ALIGNMENT.md`.
- Northbound contract `src/iot_protocol/northbound_topics.py` và canonical envelope
  `src/iot_protocol/northbound_payload.py`.
- Gateway bridge `src/edge_gateway_bridge/bridge.py`:
  - Map telemetry/status/alerts/result southbound sang `pccom/v1/...`.
  - Nhận `cmd` northbound, xác thực khóa gateway, fan-out và ký southbound.
  - Mỗi gateway một MQTT client/LWT; `--crash-after` để kiểm thử LWT.
- Mock Cloud `--northbound`, Core API `--northbound`; gateway offline đánh dấu
  thiết bị con `unknown` thay vì flood offline.
- Cấu hình `northbound` (`tenant_id`, `sites`, `gateways`, `retain_status`).
- Hỗ trợ mTLS cho simulator/bridge/cloud: `broker.ca_cert`, `broker.client_cert`,
  `broker.client_key`; `broker.tls_insecure` chỉ dành cho lab.
- SEC 01 theo gateway-level per-device authorization:
  - Bridge có identity riêng `bridge-s01`/`bridge-s02`; `generate-pki.sh` cấp cert riêng.
  - `acl.devices` cấp bridge đọc wildcard southbound trong site, ghi command và northbound,
    không dùng credential gateway cho bridge.
  - `deploy/mosquitto/aclfile.example` bổ sung mẫu bridge identity.
- `Mqtt5Client` xử lý PUBACK/SUBACK reason code `>= 0x80` là thất bại; helper
  `_reason_value` chuẩn hóa paho `ReasonCode` (không `int()` trực tiếp).
- Bridge xử lý command trên worker thread để publish chờ PUBACK không deadlock luồng mạng paho.

### Changed

- ACL gateway/dispatcher bổ sung `status`/`alerts`; `smoke.sh` kiểm tra bridge ACL.
- `Mqtt5Client.set_will` nhận `retain` để tương thích broker
  `retain_available false`.

### Tests

- 47 unit test pass, gồm regression reason code dùng `paho.mqtt.ReasonCode` thật.
- E2E northbound command/ack/telemetry/status và LWT gateway đã kiểm chứng với
  `broker.emqx.io`.
- E2E local Mosquitto: southbound đầy đủ, northbound command/ack/telemetry/status/LWT,
  reject branches và multi-gateway LWT độc lập.
- Lab ACL/TLS smoke pass với `LAB_MQTT_IMAGE=eclipse-mosquitto:2.0`; image mặc định
  `eclipse-mosquitto:2.1.2-alpine` bị `Exited (139)` trên môi trường Windows/WSL Docker.
- Full mTLS E2E: bridge `bridge-s01` → thiết bị → bridge → Cloud `dispatcher`;
  telemetry/status/command/ack pass, `status=executed`, `observed=42`.
- Bridge LWT gateway offline qua mTLS pass. Broker-level per-device isolation vẫn là
  residual risk đã chấp nhận.

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
  - `docker-compose.dev.yml`, `deploy/mosquitto/mosquitto.conf`.
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
- Đổi tên `docker-compose.yml` thành `docker-compose.dev.yml` cho broker simulator và cập nhật lệnh `docker compose -f` trong tài liệu.

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
