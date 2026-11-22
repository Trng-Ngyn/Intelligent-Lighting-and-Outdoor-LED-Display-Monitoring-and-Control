# BÁO CÁO KIỂM THỬ MQTT 5 E2E VÀ LWT

> **Ngày kiểm thử:** 14/11/2026  
> **Môi trường:** Windows, Python 3.11.15, paho-mqtt 2.1.0  
> **Broker:** `broker.emqx.io:1883` (MQTT 5, không TLS, không auth)  
> **Cấu hình:** `tests/fixtures/simulator.test.json`  
> **Kết quả tổng hợp:** PASS  
> **Log gốc:** [`logs/`](logs/)

---

## I. PHẠM VI KIỂM THỬ

| Hạng mục | Mô tả |
| :--- | :--- |
| Unit test | Topic, chữ ký, header, replay, cấu hình simulator |
| E2E telemetry | Thiết bị publish telemetry, Cloud nhận và xác thực chữ ký |
| E2E status | Online/offline retained, Cloud theo dõi thay đổi trạng thái |
| E2E command/result | Cloud gửi lệnh dim có ký, thiết bị thực thi, result cùng `correlation_id` |
| LWT | Crash không DISCONNECT, broker phát Will `offline` retained |
| Chất lượng mã | flake8 và compileall |

Phase 1 chưa bao phủ kiểm thử tải 52 thiết bị và xác thực broker thật. Phase 2 (mục IX) bổ sung
Mosquitto local, northbound bridge, reject branches, multi-gateway và ACL/TLS lab.

---

## II. LỆNH KIỂM THỬ

### 1. Unit test

```powershell
$env:PYTHONUTF8 = "1"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

Kết quả:

```text
Ran 25 tests in 0.033s
OK
```

Các nhóm test:

- `TopicTests`: build/parse topic, wildcard, từ chối segment không hợp lệ.
- `SigningTests`: canonical string, HMAC, khóa thiết bị khác nhau.
- `ReplayGuardTests`: cửa sổ thời gian, ID trùng, dọn bộ nhớ.
- `HeaderTests`: đủ/thiếu/trùng header, sai chữ ký, replay.
- `ConfigTests`: 52 thiết bị, env override, secret ngắn bị từ chối.

### 2. Flake8 và compile

```powershell
.\.venv\Scripts\python.exe -m compileall -q src\iot_protocol src\edge_simulator src\backend tools\mqtt5_probe.py tests
.\.venv\Scripts\flake8.exe src\iot_protocol src\edge_simulator src\backend tools\mqtt5_probe.py tests
```

Kết quả: không có lỗi.

### 3. E2E telemetry + command + result

```powershell
# Terminal 1: Mock Cloud, tự gửi dim sau 6 giây
.\.venv\Scripts\python.exe src\backend\mock_cloud_service.py `
  --config tests\fixtures\simulator.test.json `
  --dim-device LGT_NODE_001 --dim-value 65 --send-delay 6 --run-seconds 16

# Terminal 2: Simulator chạy 18 giây
.\.venv\Scripts\python.exe src\edge_simulator\virtual_lighting_network.py `
  --config tests\fixtures\simulator.test.json --run-seconds 18
```

### 4. LWT

```powershell
# Dọn retained status cũ
.\.venv\Scripts\python.exe tools\mqtt5_probe.py `
  --config tests\fixtures\simulator.test.json clear-status

# Terminal 1: probe chỉ theo dõi status
.\.venv\Scripts\python.exe tools\mqtt5_probe.py `
  --config tests\fixtures\simulator.test.json watch --status-only --run-seconds 22

# Terminal 2: simulator crash sau 8 giây, không DISCONNECT
.\.venv\Scripts\python.exe src\edge_simulator\virtual_lighting_network.py `
  --config tests\fixtures\simulator.test.json --crash-after 8
```

---

## III. KẾT QUẢ E2E

### 1. Trạng thái online

```text
19:57:59.384 mock_cloud STATUS_CHANGE LGT_NODE_001 status=online correlation_id=c17850c8-ba0b-4da0-8713-350fc1a07cd8
19:57:59.956 mock_cloud STATUS_CHANGE LGT_NODE_002 status=online correlation_id=9c28166e-40fb-4ee7-9e0f-bd8ffe449a0e
19:58:00.633 mock_cloud STATUS_CHANGE DSP_LED_001 status=online correlation_id=4a2fb2cc-c307-4ae4-9bda-93cf70b111e6
```

Kết luận: 3/3 thiết bị publish status online retained, Cloud nhận đủ.

### 2. Telemetry

```text
19:58:00.539 TELEMETRY LGT_NODE_001 seq=1 power_w=51.0 voltage_v=218.5 temp_c=46.6 lux=136.7
19:58:05.624 TELEMETRY LGT_NODE_001 seq=2 power_w=63.51 voltage_v=220.2 temp_c=52.0 lux=77.2
19:58:10.586 TELEMETRY LGT_NODE_001 seq=3 power_w=65.14 voltage_v=220.4 temp_c=51.1 lux=249.6
```

Kết luận:

- Chu kỳ telemetry thực tế khoảng 5 giây, khớp `telemetry_interval_sec = 5`.
- Sau khi dim xuống 65, `power_w` tăng từ khoảng 51 W lên 63–65 W, phản ánh đúng thay đổi
  trạng thái.
- Mọi bản tin đều được Cloud xác thực chữ ký thành công.

### 3. Command và result

```text
19:58:03.134 mock_cloud COMMAND_TX value=65 correlation_id=3596b597-897c-4d74-88d9-5e33d1147ccd
19:58:03.134 simulator  COMMAND RX correlation_id=3596b597-897c-4d74-88d9-5e33d1147ccd value=65 action=DIM
19:58:03.144 simulator  RESULT correlation_id=3596b597-897c-4d74-88d9-5e33d1147ccd status=EXECUTED
19:58:03.396 mock_cloud COMMAND_RESULT status=EXECUTED observed=65 correlation_id=3596b597-897c-4d74-88d9-5e33d1147ccd
```

Kết luận:

- Cloud gửi lệnh có `Correlation Data`, `Response Topic`, `Message Expiry Interval = 60`.
- Thiết bị nhận và thực thi trong cùng mili-giây (log 03.134).
- Result được publish lúc 03.144, Cloud nhận lúc 03.396.
- **Độ trễ command → result phía Cloud: 262 ms.**
- `correlation_id` của lệnh và result trùng khớp tuyệt đối.
- `observed_value = 65` khớp giá trị yêu cầu.

> Trước khi tối ưu `wait_for_ack`, cùng kịch bản mất khoảng 5 giây do chờ PUBACK trên broker
> công cộng. Sau khi bỏ chờ ack cho telemetry/status/result, độ trễ giảm còn dưới 0,3 giây.

---

## IV. KẾT QUẢ LWT

### 1. Mốc thời gian

```text
19:58:41.114 simulator  CRASH MODE bật: sẽ thoát không DISCONNECT sau 8.0s
19:58:49.117 simulator  CRASH MODE: thoát tiến trình không gửi DISCONNECT device=LGT_NODE_001
19:58:49.542 probe      PROBE_STATUS LGT_NODE_001 payload=offline
19:58:49.546 probe      PROBE_STATUS LGT_NODE_002 payload=offline
19:58:49.546 probe      PROBE_STATUS DSP_LED_001 payload=offline
```

### 2. Độ trễ phát hiện offline

| Thiết bị | Thời điểm crash | Thời điểm probe nhận offline | Độ trễ |
| :--- | :--- | :--- | ---: |
| `LGT_NODE_001` | 19:58:49.117 | 19:58:49.542 | **425 ms** |
| `LGT_NODE_002` | 19:58:49.117 | 19:58:49.546 | **429 ms** |
| `DSP_LED_001` | 19:58:49.117 | 19:58:49.546 | **429 ms** |

Kết luận:

- Broker phát hiện TCP đóng và phát Will gần như tức thời.
- Độ trễ dưới 0,5 giây, đạt yêu cầu ≤ 30 giây.
- Will payload `offline`, retained, QoS 1, `Will Delay Interval = 0`.
- `correlation_id` của LWT là ID đã đăng ký lúc CONNECT; điều này đúng đặc tả và đã được
  ghi chú trong tài liệu giao thức.

### 3. Graceful shutdown

Khi chạy `--run-seconds`, simulator publish `status offline` retained trước khi DISCONNECT:

```text
19:58:18.634 STATUS offline LGT_NODE_001
19:58:18.991 STATUS offline LGT_NODE_002
19:58:19.317 STATUS offline DSP_LED_001
```

Cloud/probe nhận được trạng thái offline ngay, không phụ thuộc LWT.

---

## V. ĐỐI CHIẾU YÊU CẦU

| Yêu cầu | Kết quả | Bằng chứng |
| :--- | :---: | :--- |
| MQTT 5 với User Properties | PASS | Log header/correlation_id, unit test |
| Taxonomy topic v1 | PASS | Unit test + log topic thực tế |
| QoS 1 cho telemetry/command/result/status/alert | PASS | Cấu hình publish, log không lỗi |
| Chỉ status retained | PASS | Status online/offline retained; telemetry/command/result retain false |
| Lệnh có Correlation Data/Response Topic/Expiry 60s | PASS | `COMMAND_TX` và `COMMAND RX` |
| HMAC-SHA256 theo thiết bị | PASS | Cloud xác thực thành công; unit test sai chữ ký bị từ chối |
| Chống replay ±30s + cache ID | PASS | Unit test `ReplayGuardTests`, `HeaderTests` |
| LWT offline ≤ 30s | PASS | Đo thực tế 425–429 ms |
| Graceful offline | PASS | Log status offline trước DISCONNECT |
| Không hard-code secret | PASS | Đọc từ config/env; `.gitignore` chặn `config.json` |
| Flake8/compile | PASS | Không lỗi |

---

## VI. RỦI RO VÀ KHUYẾN NGHỊ

1. **Broker công cộng:** `broker.emqx.io` không phù hợp production; số đo có thể dao động.
   Cần kiểm thử lại với Mosquitto local/TLS và ACL trước khi nghiệm thu.
2. **Docker daemon chưa chạy:** chưa kiểm thử broker local trong môi trường hiện tại. Cần chạy
   `docker compose -f docker-compose.dev.yml up -d` và lặp lại kịch bản E2E/LWT.
3. **Firmware ESP32:** PubSubClient hiện dùng MQTT 3.1.1, chưa gửi được User Properties MQTT 5.
   Cần gateway/bridge hoặc nâng cấp thư viện trước khi tích hợp phần cứng thật.
4. **Đồng hồ thiết bị:** replay window ±30 giây yêu cầu đồng bộ NTP. Thiết bị lệch giờ sẽ bị
   từ chối với `SEC_REPLAY_DETECTED`.
5. **Retained status mồ côi:** khi xóa thiết bị khỏi cấu hình, cần chạy `clear-status` để dọn
   retained status cũ.

---

## VII. LOG GỐC

| File | Nội dung |
| :--- | :--- |
| [`logs/final_e2e_cloud.err.log`](logs/final_e2e_cloud.err.log) | Log Cloud: status, telemetry, command TX, result |
| [`logs/final_e2e_sim.err.log`](logs/final_e2e_sim.err.log) | Log Simulator: kết nối, LWT, telemetry, command RX, result, offline |
| [`logs/final_lwt_probe.err.log`](logs/final_lwt_probe.err.log) | Log probe: status online/offline dùng đo LWT |
| [`logs/final_lwt_sim.err.log`](logs/final_lwt_sim.err.log) | Log Simulator trong kịch bản crash |

Log được ghi bằng UTF-8. Trên Windows PowerShell 5.1, đọc bằng
`Get-Content <file> -Encoding UTF8` để hiển thị đúng tiếng Việt.

---

## VIII. KẾT LUẬN

Giao thức MQTT 5 v1 đã được triển khai và kiểm chứng thực tế:

- Bản tin có định danh, chữ ký và chống replay.
- Lệnh dim được gửi/nhận/phản hồi đúng trong khoảng 262 ms.
- LWT phát hiện offline trong khoảng 0,43 giây, đạt ngân sách 30 giây.
- Unit test, flake8 và compile đều pass.

Phase 2 tại mục IX đã kiểm thử Mosquitto local + TLS/ACL. Bước tiếp theo là tích hợp firmware
MQTT 5.

---

## IX. PHASE 2 — LOCAL MOSQUITTO, NORTHBOUND, ACL/TLS

> **Ngày kiểm thử:** 16/11/2026
> **Broker local:** `eclipse-mosquitto:2.0`, `docker-compose.dev.yml`
> **Lab:** `eclipse-mosquitto:2.0` listener `8883`/`8884`, cert `gw-001`, `bridge-s01` và `dispatcher`
> **Kết quả tổng hợp:** PASS; SEC 01 chốt gateway-level per-device authorization

### 1. Unit test và chất lượng mã

```text
Ran 47 tests in 0.044s
OK
```

`flake8` cho `src/edge_simulator/config.py`, `src/edge_simulator/mqtt_client.py`,
`src/edge_gateway_bridge/bridge.py`, `tests/test_simulator_config.py`,
`tests/test_mqtt_client.py` và CI selector `E9,F63,F7,F82` đều pass.

### 2. Local southbound

Kịch bản với Mosquitto Docker pass: telemetry, status, command/result và LWT crash.
Cloud xác thực chữ ký, nhận result cùng `correlation_id`; LWT phát `offline` sau crash.

### 3. Local northbound

Core API `--northbound` → bridge → simulator → `ack`; Cloud nhận telemetry/status.
Bridge crash phát gateway `offline`; Cloud đánh dấu thiết bị con `unknown`.

### 4. Reject branches và multi-gateway

- Expired command, action không hỗ trợ, thiếu `requested_value`, unknown target đều bị bridge
  từ chối trước khi fan-out.
- Cloud log `ACK_RX status=rejected` hoặc `ACK_RX_UNKNOWN`; bridge log `ACK_REJECT`.
- `gw-001` crash (`--crash-after 7`) → gateway offline; `gw-002` vẫn gửi telemetry độc lập,
  sau đó graceful offline. Không có flood offline thiết bị con.

### 5. Lab ACL/TLS

`bash smoke.sh` pass với `LAB_MQTT_IMAGE=eclipse-mosquitto:2.0`:

```text
API: authorized cert; unknown serial, missing/revoked cert, wrong CA and hostname checked.
Client bridge-s01 received PUBACK (Mid: 1, RC:16)
Warning: Publish 1 failed: Not authorized.
Client bridge-s01 received PUBACK (Mid: 1, RC:135)
MQTT 5: valid publish, command service, bridge ACL, cross-site denial and rejected CA/CRL checked.
```

Các điểm phát hiện:

- Image lab mặc định `eclipse-mosquitto:2.1.2-alpine` bị `Exited (139)` sau khi load config
  trong môi trường Windows/WSL Docker; phải override `LAB_MQTT_IMAGE=eclipse-mosquitto:2.0`.
- Cổng `8884` nằm trong excluded port range của Windows; khi publish ra host phải dùng cổng khác
  (ví dụ `18884`) hoặc chạy client trong Docker network.
- Cert lab dùng CN `mqtt.dev.pccom.test`, không khớp `127.0.0.1`; client test cần
  `broker.tls_insecure=true` hoặc thêm hosts entry.
- `RC:16` là PUBACK không có subscriber nhưng được phép; `RC:135` là Not authorized, đúng cho
  cross-site/denied.
- `bridge-s01` được phép ghi `commands/v1/SITE_01/.../dim` và
  `pccom/v1/t1/s01/gw-001/status`, nhưng bị chặn khi ghi telemetry thiết bị hoặc topic của site
  khác. Đây là kiểm chứng cho SEC 01 gateway-level authorization.

### 6. SEC 01 — Bridge identity riêng và full mTLS E2E

SEC 01 được xử lý theo hướng **gateway-level per-device authorization**:

- Bridge dùng identity riêng `bridge-s01`/`bridge-s02` (cert riêng do `generate-pki.sh` cấp),
  không dùng credential của `gw-001`.
- ACL cho bridge đọc wildcard telemetry/status/alerts/result trong site, ghi command và
  northbound `pccom/v1/...` của gateway tương ứng.
- Thiết bị vẫn chỉ đọc command và ghi telemetry/status/alert/result của chính nó.
- Bridge tiếp tục xác thực HMAC từng thiết bị. Broker không cô lập tuyệt đối từng thiết bị sau
  gateway; đây là residual risk đã chấp nhận, không phải broker-level per-device ACL.

Full E2E qua mTLS với Cloud cert `dispatcher`, bridge cert `bridge-s01`, fake device cert
`gw-001` (ACL tạm chỉ trong lab):

```text
device: PUBLISH telemetry topic=telemetry/v1/SITE_01/light/LGT_LAB_001 ok=True
bridge: TELEMETRY_FORWARD device=LGT_LAB_001
cloud:  TELEMETRY_RX gateway=gw-001 device=LGT_LAB_001
cloud:  COMMAND_TX gateway=gw-001 device=LGT_LAB_001 value=42
bridge: COMMAND_RX command_id=... device=LGT_LAB_001
bridge: ACK_TX command_id=... status=executed observed=42
```

`Mqtt5Client` xử lý PUBACK/SUBACK reason code `>= 0x80` là thất bại nên ACL deny không còn bị
coi là publish thành công. Paho `ReasonCode` không `int()` trực tiếp; code dùng helper
`_reason_value` đọc `.value`. Command được đẩy sang worker thread trước khi publish chờ PUBACK,
tránh deadlock vì callback `on_message` chạy trên luồng mạng của paho.

```text
Ran 47 tests in 0.044s
OK
```

**Giới hạn còn lại:** broker vẫn không cô lập từng thiết bị con; retained status/stale offline,
spool 24h, idempotency/receipt và load test chưa hoàn thiện.

### 7. Log Phase 2

| File | Nội dung |
| :--- | :--- |
| [`logs/phase2_local_south_cloud.err.log`](logs/phase2_local_south_cloud.err.log) | Local southbound Cloud |
| [`logs/phase2_local_south_sim.err.log`](logs/phase2_local_south_sim.err.log) | Local southbound simulator |
| [`logs/phase2_local_north_cloud.err.log`](logs/phase2_local_north_cloud.err.log) | Local northbound Cloud |
| [`logs/phase2_local_north_bridge.err.log`](logs/phase2_local_north_bridge.err.log) | Local northbound bridge |
| [`logs/phase2_local_north_sim.err.log`](logs/phase2_local_north_sim.err.log) | Local northbound simulator |
| [`logs/phase2_local_reject_cloud.err.log`](logs/phase2_local_reject_cloud.err.log) | Cloud log reject branches |
| [`logs/phase2_local_reject_bridge.err.log`](logs/phase2_local_reject_bridge.err.log) | Bridge log reject branches |
| [`logs/phase2_multi_cloud.err.log`](logs/phase2_multi_cloud.err.log) | Multi-gateway Cloud |
| [`logs/phase2_multi_bridgeA.err.log`](logs/phase2_multi_bridgeA.err.log) | `gw-001` crash |
| [`logs/phase2_multi_bridgeB.err.log`](logs/phase2_multi_bridgeB.err.log) | `gw-002` độc lập |
| [`logs/phase2_lab_cloud.err.log`](logs/phase2_lab_cloud.err.log) | Cloud qua mTLS |
| [`logs/phase2_lab_bridge.err.log`](logs/phase2_lab_bridge.err.log) | Bridge qua mTLS + LWT |
| [`logs/phase2_lab_smoke.log`](logs/phase2_lab_smoke.log) | Smoke ACL/TLS |

### 8. Kết luận Phase 2

Runtime Phương án C đã pass local southbound, local northbound, reject branches,
multi-gateway LWT, lab ACL/TLS và full mTLS E2E với bridge identity riêng.
SEC 01 đã chốt theo gateway-level per-device authorization. Việc còn mở trước nghiệm thu đầy đủ
là canonical contract, retained status/stale offline policy, spool/idempotency và load test.
