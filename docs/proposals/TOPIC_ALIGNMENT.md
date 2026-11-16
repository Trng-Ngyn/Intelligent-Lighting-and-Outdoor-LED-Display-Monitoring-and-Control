# QUYẾT ĐỊNH KIẾN TRÚC TOPIC MQTT: PHƯƠNG ÁN C

> **Trạng thái:** Đã chốt Phương án C; Phase 1 (northbound contract + ACL) và Phase 2 (gateway bridge + northbound Cloud/Core API) đã triển khai; Phase 3 (spool/receipt/scale) còn lại  
> **Quyết định:** C là kiến trúc đích theo RFP; A chỉ là ngoại lệ direct-device  
> **Phạm vi:** topic MQTT 5 cho telemetry, lệnh dim, ack/result, status/LWT, alerts và receipt  
> **Căn cứ:** RFP PCCOM, ACL + compose lab của Tech Lead, `src/iot_protocol/topics.py`, mock cloud/Core API/simulator/probe, đặc tả MQTT 5 và contracts  
> **Ngày:** 16/11/2026

---

## 1. Kết luận ngắn

1. **Hai thiết kế không tương thích trực tiếp.** Tech Lead dùng namespace **tenant-first, cấp gateway**; IoT dùng namespace **category-first, cấp thiết bị**.
2. Baseline Tech Lead ban đầu **không có** topic `status`, `alerts`; Phase 1 đã bổ sung ACL cho hai nhánh này. IoT **không có** `tenant`, `gateway_id` và **không có** `receipt`.
3. `ack` của Tech Lead gần với `command result` của IoT, nhưng `receipt` là loại bản tin riêng (Cloud → Gateway xác nhận đã lưu/cách ly telemetry), không có tương ứng bên IoT.
4. Repo còn **định dạng thứ ba** trong firmware (`pccom/lighting/...`) và **mô hình danh tính thứ ba** trong `docs/data_contracts/` (UUID `tenant_id/site_id/asset_id/device_id`). Cần chốt luôn để tránh "thống nhất hai bên" nhưng còn lệch với firmware/contracts.
5. **LWT là điểm quyết định kiến trúc:** mỗi kết nối MQTT chỉ có một Will. Nếu chỉ gateway kết nối broker thì Cloud chỉ có LWT cấp gateway, **không thể** có LWT riêng cho từng đèn nếu không có kết nối riêng hoặc gateway tự tổng hợp status.
6. **Chốt Phương án C (hai lớp, C chuẩn hóa).** Giữ topic thiết bị ↔ gateway của IoT; gateway ↔ Cloud dùng namespace tenant-first của Tech Lead; bổ sung `status`/`alerts` qua bridge. Đây là quyết định kiến trúc, không phải phương án tạm.
7. **A chỉ là ngoại lệ** khi mỗi đèn/LED kết nối MQTT trực tiếp với cert/ACL riêng và bên mua yêu cầu broker-level per-device isolation. B không phù hợp với kiến trúc gateway/edge của RFP.
8. **Lý do chọn C không phải vì độ dễ:** C bảo toàn trust boundary device ↔ gateway ↔ cloud, đáp ứng yêu cầu tương quan sự cố gateway, scale theo 10.000 tài sản và cho phép thay đổi thiết bị/cloud độc lập.

### 1.1. Căn cứ RFP cho quyết định C

| Căn cứ RFP | Nội dung | Hàm ý cho kiến trúc/topic |
| :--- | :--- | :--- |
| §6, dòng 144 | Thiết bị hiện trường kết nối **qua controller hoặc gateway biên** tới lớp ingestion có xác thực. | Gateway là điểm gom cụm; C mô hình hóa đúng vật lý và trust boundary. |
| §6, dòng 148 | Lớp biên có offline queue, watchdog, secure storage, signed update, clock sync. | C đặt trách nhiệm spool/fallback/an toàn tại gateway. |
| ARC 02, dòng 373 | Adapter nhà cung cấp chuẩn hóa từng họ thiết bị vào hợp đồng dự án; MQTT chỉ là transport. | Bridge của C chính là adapter; cloud không bị coupling vào taxonomy thiết bị. |
| Dòng 446, 540, 545 | Phải **tương quan mất gateway** thành sự cố hạ tầng, không tràn ngập cảnh báo từng tài sản con. | C có gateway-level LWT/status; device con chuyển `unknown/stale` thay vì `offline` giả. |
| Dòng 45 | Góc nhìn vận hành duy nhất bao gồm **gateway**. | Gateway là first-class asset trong northbound. |
| SEC 01, dòng 165 | Định danh thiết bị duy nhất và phân quyền theo từng thiết bị; không dùng mật khẩu mặc định dùng chung. | C giữ device identity ở southbound/payload; gateway thực thi per-device authz. Nếu bên mua yêu cầu broker-level per-device ACL thì mới cần A/B. |
| LGT 01/02, dòng 87-88; CTL 01/02, dòng 385-387 | Phân biệt commanded/reported/unknown; `ack` tách khỏi trạng thái vật lý đã xác minh; chống replay/idempotency. | C tách `cmd` / `ack` / `status`; `command_id` xuyên suốt. |
| LGT 06, dòng 92; OPS 01, dòng 170 | Cảnh báo sự cố và giám sát availability. | C có nhánh `alerts` và status theo thiết bị/gateway. |
| OPS 02, dòng 171; AT 05, dòng 193 | Đệm telemetry 24h, đối soát trùng và lệnh hết hạn sau mất WAN. | C có gateway spool, sequence và `receipt`/reconciliation. |
| DAT 01, dòng 471; DAT, dòng 475-477 | Schema có version, tenant/site/asset/device, source time, quality, command result. | C dùng canonical envelope ở northbound; device identity trong payload. |
| NFR, dòng 516 | 10.100 tài sản, khoảng 168 msg/s. | C gom northbound theo gateway; topic cardinality theo gateway thay vì từng thiết bị. |
| Dòng 150 | MQTT 5, schema, QoS, command ID, expiry, chống replay, ack, idempotency; broker giao nhận không phải bằng chứng thực thi. | C định nghĩa semantic rõ giữa transport, ack và verified state. |

---

## 2. Hiện trạng và mọi nơi đang dùng từng định dạng

### 2.1. Tech Lead — `pccom/v1/{tenant}/{site}/{gateway_id}/{category}`

Mô hình: tenant → site → gateway → category. Gateway là chủ thể xác thực mTLS và là đơn vị ACL; danh tính đèn/LED nằm trong payload (`asset_id`/`device_id`).

| Nơi dùng | Nội dung / vai trò |
| :--- | :--- |
| `acl.devices:1-15` | `gw-001`, `gw-002`; mỗi gateway ghi `telemetry`/`ack`/`status`/`alerts`; đọc `cmd`/`receipt` |
| `acl.service:1-8` | `dispatcher` đọc `telemetry`/`ack`/`status`/`alerts`; ghi `cmd`/`receipt` theo site |
| `compose.yml:10-12` | Mount `mosquitto.conf`, `acl.devices`, `acl.service` vào broker lab |
| `mosquitto.conf:9-32` | Hai listener mTLS 8883/8884; `per_listener_settings true` ở dòng 1 |
| `mosquitto.conf:20,32` | Gắn `acl.devices` cho listener thiết bị, `acl.service` cho listener dịch vụ |
| `mosquitto.conf:3` | `retain_available false` — **không cho phép retained message** |
| `smoke.sh:58-68` | Topic test thực tế: `pccom/v1/t1/s01/gw-001/telemetry`, `.../s02/gw-002/telemetry`, `.../gw-001/cmd` |
| `generate-pki.sh:71-75` | Danh tính cert: `URN:pccom:dev:t1:s01:gw-001`, `...:t1:s02:gw-002`, service `dispatcher` |
| `contracts/README.md:7-16` | Mô hình dữ liệu gateway: `tenant_id + gateway_id + message_id`; `receipt`, `command`, `ack` |
| `contracts/telemetry.schema.json:18-47,100-114` | Bắt buộc `tenant_id`, `site_id`, `gateway_id`, `asset_id`, `message_id`, ... |
| `contracts/command.schema.json:25-60,120-137` | Bắt buộc `tenant_id`, `site_id`, `gateway_id`, `command_id`, `asset_id`; target có `asset/group/zone` |
| `contracts/ack.schema.json:25-48,91-102` | Ack cấp gateway + `asset_id`; trạng thái `acknowledged/executed/verified/rejected/expired/failed/unknown` |
| `contracts/receipt.schema.json:25-68` | Receipt Cloud → Gateway: `tenant_id`, `site_id`, `gateway_id`, `message_id`, `stored/quarantined` |
| `README.md:8-9,89-100` | Mô tả lab: gateway ghi topic được cấp, dispatcher phát lệnh, chặn ghi chéo site |

**Đặc điểm quan trọng**

- Baseline ban đầu không có `status`/`alerts`/LWT trong ACL; Phase 1 đã thêm `status`/`alerts`, nhưng `retain_available false` vẫn giữ nên status northbound hiện non-retained.
- `cmd` là **một dòng lệnh chung cho gateway**, không tách `/dim`; payload phải chỉ định `asset_id`/target.
- `ack` là kết quả ứng dụng cấp gateway/asset; `receipt` là xác nhận lưu dữ liệu, **không phải** kết quả lệnh.
- `retain_available false` mâu thuẫn trực tiếp với mô hình `status` retained của IoT.

### 2.2. IoT — `{category}/v1/{site_id}/{device_type}/{device_id}`

Mô hình: category → version → site → device_type → device_id. Mỗi thiết bị là một MQTT client, có LWT, status và khóa HMAC riêng.

| Nơi dùng | Nội dung / vai trò |
| :--- | :--- |
| `src/iot_protocol/topics.py:7-12` | Docstring taxonomy 5 nhóm: telemetry, commands, status, alerts; result nằm dưới commands |
| `src/iot_protocol/topics.py:23-31` | `TOPIC_VERSION = "v1"`, segment pattern, `light/led_display/gateway` |
| `src/iot_protocol/topics.py:75-109` | Builders: telemetry, command dim, command result, status, alerts |
| `src/iot_protocol/topics.py:112-138` | Wildcards: `telemetry/v1/+/+/+`, `status/v1/+/+/+`, `alerts/v1/+/+/+`, `commands/v1/+/+/+/dim`, `.../dim/result` |
| `src/iot_protocol/topics.py:161-201` | Parse/validate topic; không có tenant/gateway segment |
| `src/backend/mock_cloud_service.py:57-66,179-185` | Subscribe telemetry/status/alerts/result wildcard |
| `src/backend/mock_cloud_service.py:390-439` | Cloud publish alert vào `alerts/v1/...` |
| `src/backend/mock_cloud_service.py:441-514` | Cloud gửi dim vào `commands/v1/.../dim`, response topic `.../dim/result` |
| `src/backend/core_api.py:42,162-249` | Core API gửi dim theo từng thiết bị, cùng cặp topic command/result |
| `src/edge_simulator/simulator_device.py:48-54,87-101` | Mỗi `SimulatorDevice` giữ 5 topic riêng |
| `src/edge_simulator/simulator_device.py:132-142` | LWT riêng cho từng thiết bị tại `status/v1/{site}/{type}/{id}` |
| `src/edge_simulator/simulator_device.py:156-159` | Subscribe command riêng của thiết bị |
| `src/edge_simulator/simulator_device.py:171-203` | Publish online/offline retained |
| `src/edge_simulator/simulator_device.py:205-281` | Publish telemetry |
| `src/edge_simulator/simulator_device.py:503-553` | Publish result dưới `commands/.../dim/result` |
| `src/edge_simulator/simulator_device.py:555-607` | Publish alert dưới `alerts/...` |
| `tools/mqtt5_probe.py:53-62,126-138` | Probe subscribe 4 wildcard |
| `tools/mqtt5_probe.py:268-330` | Probe gửi dim và response topic |
| `tools/mqtt5_probe.py:332-368` | Probe clear retained status |
| `tests/test_iot_protocol.py:55-88` | Test build toàn bộ topic + wildcard |
| `tests/test_iot_protocol.py:107-128` | Test parse topic, từ chối wildcard/sai version |
| `deploy/mosquitto/aclfile.example:5-34` | ACL mẫu IoT: cloud_ingest, gateway_SITE_01, từng light/LED |
| `docs/specifications/MQTT5_COMMUNICATION_PROTOCOL.md:85-91` | Bảng QoS/retain cho 5 nhóm |
| `docs/specifications/MQTT5_COMMUNICATION_PROTOCOL.md:106-150` | Cấu trúc, ràng buộc segment, wildcard, ví dụ |
| `docs/specifications/MQTT5_COMMUNICATION_PROTOCOL.md:224-226,252-262,285-290,312-316,343-347` | Topic từng payload telemetry/command/result/status/alert |
| `docs/specifications/MQTT5_COMMUNICATION_PROTOCOL.md:385-400,425-455` | LWT/offline và ACL mẫu |
| `docs/test_reports/MQTT5_E2E_REPORT.md:188,191` | Xác nhận taxonomy v1 và log topic thực tế |
| `docs/test_reports/logs/*.log` | Log E2E/LWT/ACL chứa topic v1 thực tế; ví dụ `acl_mosquitto_test.log:5,29,56` |

**Đặc điểm quan trọng**

- Không có `tenant` ở bất kỳ đâu trong code/config (đã kiểm tra `src/`, `tools/`, `tests/`).
- Không có `gateway_id`; `gateway` chỉ là một giá trị `device_type` được phép (`topics.py:31`), không phải chủ thể gom cụm.
- `commands` chỉ có nhánh `/dim`; `SWITCH` dùng chung topic dim và phân biệt bằng `action` trong payload.
- `status` retained + LWT **theo từng thiết bị** là hành vi đã được kiểm thử E2E.

### 2.3. Định dạng legacy trong firmware và mô hình W3-DE

Đây không phải hai thiết kế đang so sánh, nhưng nếu không chốt sẽ tiếp tục lệch:

| Nơi dùng | Nội dung |
| :--- | :--- |
| `src/firmware_esp32/include/config.h:27-31` | Topic legacy: `pccom/lighting/{SITE_ID}/{ASSET_ID}/{telemetry\|heartbeat\|command\|result}` |
| `src/firmware_esp32/README.md:53-56` | Tài liệu hóa đúng định dạng legacy trên |
| `src/firmware_esp32/src/main.cpp:52,127,184` | Publish result/telemetry, subscribe command theo các macro legacy |
| `docs/data_contracts/schemas/telemetry.lighting.v1.schema.json:13-48` | `tenant_id`, `site_id`, `asset_id`, `device_id` kiểu UUID 36 ký tự |
| `docs/data_contracts/schemas/command.request.v1.schema.json:13-70,132-142` | `tenant_id`, `site_id`, `command_id` UUID; target `asset/group/zone` |
| `docs/data_contracts/schemas/command.result.v1.schema.json:13-48,209-217` | `tenant_id`, `site_id`, `asset_id`, `device_id` UUID |

Hai bộ contract trong repo cũng khác nhau: `contracts/` dùng `gateway_id` + ID dạng slug; `docs/data_contracts/` dùng UUID và không có `gateway_id` trong telemetry/command. **Cần chọn một bộ làm chuẩn** trước khi chốt topic.

---

## 3. Bảng ánh xạ từng loại message

| Loại message | Tech Lead (`pccom/v1/...`) | IoT (`.../v1/...`) | Tương ứng? | Thiếu / khác |
| :--- | :--- | :--- | :---: | :--- |
| **Telemetry** | `pccom/v1/{tenant}/{site}/{gateway}/telemetry`; gateway → Cloud; QoS 1, non-retained; payload có `asset_id` (contracts) | `telemetry/v1/{site}/{type}/{id}`; thiết bị → Cloud; QoS 1, non-retained | Có, cùng dữ liệu | Tech gom nhiều thiết bị vào topic gateway; IoT tách topic từng thiết bị. IoT thiếu tenant/gateway; Tech thiếu device trong topic |
| **Lệnh dim** | `pccom/v1/{tenant}/{site}/{gateway}/cmd`; Cloud → gateway; QoS 1; payload target asset/group + action | `commands/v1/{site}/{type}/{id}/dim`; Cloud → thiết bị; QoS 1; action DIM/SWITCH trong payload | Có, cùng nghiệp vụ | Tech không có `/dim`; gateway phải fan-out. IoT không có tenant/gateway; không có topic lệnh SWITCH riêng |
| **Ack / result** | `pccom/v1/{tenant}/{site}/{gateway}/ack`; gateway → Cloud; QoS 1 | `commands/v1/{site}/{type}/{id}/dim/result`; thiết bị → Cloud; QoS 1 | Có, nếu `ack` là kết quả lệnh | Tech dùng `ack`, IoT dùng `result`; vocabulary status khác (`EXECUTED/REJECTED/EXPIRED` vs `executed/rejected/expired/...`); Tech ack cấp gateway + asset_id |
| **Receipt** | `pccom/v1/{tenant}/{site}/{gateway}/receipt`; Cloud → gateway; QoS 1 | **Không có** | **Không** | IoT chỉ có PUBACK/QoS 1 ở tầng giao vận, không có xác nhận lưu bền/cách ly ở tầng ứng dụng |
| **Status / LWT** | **Không có topic status**; ACL không cấp; `retain_available false` | `status/v1/{site}/{type}/{id}`; thiết bị/LWT → Cloud; QoS 1, **retained**, `online/offline` | **Không** | Tech không có status, không có LWT cấp đèn; IoT có LWT từng thiết bị. Nếu chỉ gateway kết nối, broker chỉ có LWT gateway |
| **Alerts** | **Không có topic alerts** | `alerts/v1/{site}/{type}/{id}`; thiết bị/Cloud → Cloud/Probe; QoS 1, non-retained | **Không** | Tech không có kênh cảnh báo bảo mật/vận hành; IoT có mã alert và `related_correlation_id` |
| **Heartbeat (legacy)** | Không có | Không có trong taxonomy v1 | **Không** | Chỉ có trong firmware legacy `pccom/lighting/{site}/{asset}/heartbeat` |

**Kết luận ánh xạ:** telemetry, lệnh dim và ack/result có thể ánh xạ nghiệp vụ 1-1; status/LWT, alerts và receipt là các **khoảng trống thực sự**, không chỉ khác tên.

---

## 4. Kiến trúc gateway: điều đã biết và điều chưa được chốt

### 4.1. Bằng chứng hiện có

- PKI lab cấp **một cert cho mỗi gateway** (`generate-pki.sh:71-75`), không cấp cert cho từng đèn/LED.
- ACL cấp quyền theo **gateway**, không theo thiết bị (`acl.devices:1-15`); Phase 1 đã thêm `status`/`alerts` nhưng vẫn ở cấp gateway.
- Contract telemetry/command/ack đều có **đồng thời `gateway_id` và `asset_id`** (`contracts/telemetry.schema.json:18-47`, `contracts/command.schema.json:25-60`, `contracts/ack.schema.json:25-48`).
- Command có target `asset/group/zone` (`contracts/command.schema.json:54-70`), tức một lệnh có thể nhắm nhiều tài sản sau gateway.
- Smoke test chỉ kiểm tra topic cấp gateway (`smoke.sh:58-68`).

→ **Suy luận có căn cứ:** Tech Lead thiết kế gateway là **điểm gom cụm**: một gateway đại diện nhiều đèn/LED trong một site, mang một kết nối mTLS và một bộ topic. Tuy nhiên repo **không định nghĩa** số thiết bị mỗi gateway, không định nghĩa đèn có kết nối MQTT trực tiếp hay không, và không định nghĩa LWT cấp đèn.

### 4.2. Hệ quả LWT

MQTT chỉ cho phép **một Will cho mỗi CONNECT** (`src/iot_protocol/mqtt5.py`, `make_will_properties`; simulator đăng ký tại `simulator_device.py:132-142`). Vì vậy:

- Nếu **chỉ gateway** kết nối broker: Cloud chỉ nhận LWT của gateway. Muốn biết một đèn mất kết nối, gateway phải tự phát hiện (heartbeat/timeout) rồi publish status/alerts thay cho đèn.
- Nếu **từng đèn** kết nối broker: mỗi đèn có LWT riêng, nhưng cần cert/ACL/identity riêng; mô hình mTLS gateway hiện tại không đáp ứng.
- Nếu gateway vừa gom cụm vừa mở kết nối MQTT riêng cho từng đèn: có LWT từng đèn nhưng broker thấy nhiều client, và cần cấp cert/ACL cho từng client.

Đây là **quyết định kiến trúc**, không chỉ là quyết định đặt tên topic.

### 4.3. Câu hỏi chưa có câu trả lời trong repo

- Một `gateway_id` đại diện bao nhiêu đèn/LED? Có phải 1 gateway/site như `gw-001`/`gw-002`?
- Đèn/LED có kết nối MQTT trực tiếp tới broker không, hay chỉ gateway?
- Ai sở hữu LWT/status của từng đèn: broker (nếu đèn kết nối trực tiếp) hay gateway (tự tổng hợp)?
- `receipt` có bắt buộc cho telemetry spool không, hay chỉ dùng trong lab?
- `retain_available false` có phải chủ đích bảo mật, hay sẽ bật lại khi cần status retained?

Các câu hỏi này được lặp lại ở mục 8 để chủ dự án xác nhận.

---

## 5. Các phương án

### Phương án A — Một namespace chung có tenant + gateway + device

**Cấu trúc đề xuất**

```text
pccom/v1/{tenant}/{site}/{gateway_id}/{category}/{device_type}/{device_id}
```

Ví dụ:

```text
pccom/v1/t1/s01/gw-001/telemetry/light/LGT_NODE_001
pccom/v1/t1/s01/gw-001/cmd/light/LGT_NODE_001/dim
pccom/v1/t1/s01/gw-001/ack/light/LGT_NODE_001
pccom/v1/t1/s01/gw-001/status/light/LGT_NODE_001
pccom/v1/t1/s01/gw-001/alerts/light/LGT_NODE_001
```

Hoặc giữ device trong payload và topic chỉ tới gateway:

```text
pccom/v1/{tenant}/{site}/{gateway_id}/{category}
```

| Tiêu chí | Đánh giá |
| :--- | :--- |
| Ưu điểm | Một hợp đồng duy nhất; tenant nằm trong topic nên ACL tách tenant được; giữ được tiền tố gateway của Tech Lead; nếu thêm segment device thì Cloud route/lọc được theo thiết bị |
| Nhược điểm | Phải đổi toàn bộ `topics.py`, mock cloud, Core API, simulator, probe, test, ACL mẫu, đặc tả; nếu device nằm trong payload thì ACL không thể tách quyền theo thiết bị; nếu device là segment thì gateway phải được cấp wildcard, làm mất cách ly broker-level giữa các đèn sau gateway |
| File phải sửa | `src/iot_protocol/topics.py`; `src/backend/mock_cloud_service.py`; `src/backend/core_api.py`; `src/edge_simulator/simulator_device.py`; `tools/mqtt5_probe.py`; `tests/test_iot_protocol.py`; `deploy/mosquitto/aclfile.example`; đặc tả MQTT 5; firmware/bridge |
| Ảnh hưởng ACL | Tốt cho tách tenant; xấu cho tách thiết bị sau gateway (gateway phải ghi wildcard `.../{gateway}/{category}/+/+`) |
| Ảnh hưởng LWT | **Không giải quyết** LWT từng đèn nếu chỉ gateway kết nối; nếu đèn kết nối trực tiếp thì cần cert riêng |
| Wildcard | Cloud đọc `pccom/v1/{tenant}/{site}/+/telemetry/+/+` hoặc `.../telemetry` nếu device ở payload |
| Công sức | **Cao** (2-3 sprint, chạm toàn bộ E2E đang pass) |
| Rủi ro | **Cao**: regression giao thức, lệch contracts, phải làm lại bằng chứng E2E/LWT |
| Khi nào chọn | **Chỉ là ngoại lệ:** mỗi đèn/LED có kết nối MQTT + cert/ACL riêng, hoặc bên mua bắt buộc broker-level per-device isolation. Không phải đích dài hạn của RFP. |

### Phương án B — Giữ topic IoT, thêm tenant và sửa ACL phía Tech Lead

**Cấu trúc đề xuất**

```text
telemetry/v1/{tenant}/{site}/{device_type}/{device_id}
commands/v1/{tenant}/{site}/{device_type}/{device_id}/dim
commands/v1/{tenant}/{site}/{device_type}/{device_id}/dim/result
status/v1/{tenant}/{site}/{device_type}/{device_id}
alerts/v1/{tenant}/{site}/{device_type}/{device_id}
```

| Tiêu chí | Đánh giá |
| :--- | :--- |
| Ưu điểm | Giữ được mô hình thiết bị + LWT từng đèn đã kiểm thử; thay đổi code ít hơn A (chủ yếu thêm tenant vào prefix/parse); giữ HMAC theo thiết bị |
| Nhược điểm | Không có `gateway_id`, xung đột với contract Tech Lead và với mTLS cấp gateway; Tech Lead phải viết lại ACL/PKI; nếu một gateway đại diện nhiều đèn thì broker không biết đèn nào sau gateway; tenant phải có trong config/cert |
| File phải sửa | `src/iot_protocol/topics.py`; toàn bộ nơi build/parse topic (cùng danh sách như A); `acl.devices`, `acl.service`; `smoke.sh`; `generate-pki.sh` (nếu tenant lấy từ cert); đặc tả; contracts |
| Ảnh hưởng ACL | Tách tenant tốt nếu mỗi tenant một credential; nhưng ACL theo thiết bị chỉ hiệu quả nếu mỗi đèn có credential riêng. Gateway cert dùng chung sẽ phải ghi wildcard theo site, mất cách ly thiết bị |
| Ảnh hưởng LWT | **Giữ nguyên** LWT từng thiết bị nếu đèn kết nối trực tiếp; không giải quyết nếu chỉ gateway kết nối |
| Wildcard | `telemetry/v1/{tenant}/+/+/+`; cần thêm tenant vào mọi wildcard |
| Công sức | **Trung bình-cao** |
| Rủi ro | **Trung bình-cao**: phá contract gateway_id, phải làm lại lab mTLS/smoke; chưa giải quyết bài toán gateway gom cụm |
| Khi nào chọn | Chỉ khi kiến trúc thực tế là **mỗi đèn kết nối broker trực tiếp**, không có gateway gom cụm; không phù hợp RFP hiện tại. |

### Phương án C — Hai lớp: thiết bị ↔ gateway giữ IoT; gateway ↔ Cloud dùng Tech Lead

**Cấu trúc**

```text
# Southbound: thiết bị ↔ gateway (giữ nguyên IoT)
telemetry/v1/{site}/{device_type}/{device_id}
commands/v1/{site}/{device_type}/{device_id}/dim
commands/v1/{site}/{device_type}/{device_id}/dim/result
status/v1/{site}/{device_type}/{device_id}
alerts/v1/{site}/{device_type}/{device_id}

# Northbound: gateway ↔ Cloud (Tech Lead + bổ sung)
pccom/v1/{tenant}/{site}/{gateway_id}/telemetry
pccom/v1/{tenant}/{site}/{gateway_id}/cmd
pccom/v1/{tenant}/{site}/{gateway_id}/ack
pccom/v1/{tenant}/{site}/{gateway_id}/status
pccom/v1/{tenant}/{site}/{gateway_id}/alerts
pccom/v1/{tenant}/{site}/{gateway_id}/receipt   # tùy chọn, cho telemetry spool
```

Gateway (hoặc bridge cùng tiến trình) làm nhiệm vụ:

- Gom telemetry từ thiết bị, thêm `device_type/device_id/asset_id`, publish northbound.
- Nhận `cmd` northbound, ánh xạ target sang `commands/.../{device}/dim` southbound.
- Nhận `result` southbound, publish `ack` northbound với cùng `command_id`/`correlation_id`.
- Tổng hợp `status`/`alerts` southbound thành northbound; LWT gateway chỉ báo gateway mất, trạng thái từng đèn do gateway phát hiện qua heartbeat/timeout.
- Nếu cần `receipt`, Cloud gửi northbound; bridge xóa spool/xác nhận.

| Tiêu chí | Đánh giá |
| :--- | :--- |
| Ưu điểm | Giữ nguyên E2E simulator/LWT đã pass; giữ mTLS gateway và tenant của Tech Lead; tách rõ trust boundary thiết bị ↔ gateway ↔ Cloud; không phải đổi toàn bộ code simulator ngay; contracts `gateway_id + asset_id` khớp northbound; bổ sung được status/alerts/receipt mà không phá southbound |
| Nhược điểm | Có hai hợp đồng topic phải tài liệu hóa/test; cần thêm bridge; Cloud không thấy LWT từng đèn trực tiếp mà thấy status do gateway tổng hợp (trễ phụ thuộc timeout); nếu gateway chết, chỉ biết gateway offline, không biết trạng thái từng đèn cho đến khi gateway sống lại |
| File phải sửa | Không sửa code ngay; dự kiến thêm bridge (ví dụ `src/edge_gateway_bridge/`), sửa ACL lab thêm `status`/`alerts`, cập nhật đặc tả + test E2E; simulator/`topics.py` southbound giữ nguyên |
| Ảnh hưởng ACL | Northbound tách tenant/gateway rất tốt; southbound giữ ACL thiết bị hiện tại. Bridge cần quyền đọc telemetry/status/alerts/result southbound và đọc `cmd`/ghi `ack`/`status`/`alerts` northbound; thiết bị bị cấm ghi northbound |
| Ảnh hưởng LWT | Giữ LWT từng đèn southbound; northbound chỉ có LWT gateway. Cần định nghĩa timeout/heartbeat để gateway phát `offline` cho từng đèn trong ngân sách 30 giây |
| Wildcard | Southbound giữ wildcard IoT; northbound `pccom/v1/{tenant}/{site}/+/telemetry` v.v. |
| Công sức | **Trung bình-cao**: bridge + test + tài liệu; không đại tu giao thức thiết bị |
| Rủi ro | **Trung bình**: thêm thành phần mới và hai lớp cần kiểm thử; rủi ro thấp hơn A/B cho E2E hiện có; cần chốt retain/LWT và contract |
| Khi nào chọn | **Đã chốt:** gateway là điểm gom cụm và MQTT client cấp gateway, đúng như mTLS/ACL/contracts và RFP hiện tại. |

### Bảng so sánh nhanh

| Tiêu chí | A. Một namespace | B. Giữ IoT + tenant | C. Hai lớp |
| :--- | :---: | :---: | :---: |
| Giữ E2E hiện có | Thấp | Trung bình | **Cao** |
| Tách tenant | **Cao** | Cao (nếu thêm tenant) | **Cao** |
| Tách thiết bị sau gateway | Trung bình (tùy segment) | Thấp | **Cao** (southbound) |
| LWT từng đèn | Không (nếu gateway-only) | Có (nếu direct) | **Có** (southbound) |
| Có status/alerts/receipt | Phải thêm | Phải thêm status/alerts; không có receipt | **Có** (northbound) |
| Công sức | Cao | Trung bình-cao | Trung bình-cao |
| Rủi ro | Cao | Trung bình-cao | **Trung bình** |

---

## 6. Quyết định: Phương án C

**Chốt Phương án C.** Đây là kiến trúc đích; các mục dưới đây là chi tiết triển khai C đã được chủ dự án chốt, **không phải lựa chọn lại A/B**:

1. `gw-001`/`gw-002` là gateway gom nhiều đèn/LED (một MQTT client cấp gateway).
2. Cloud chỉ cần kết nối/ACL cấp gateway, không cần broker-level isolation từng đèn northbound.
3. Chấp nhận status từng đèn do gateway tổng hợp (trễ ≤ 30 giây), không yêu cầu LWT broker-level cho từng đèn.

A chỉ được dùng khi có quyết định thay đổi kiến trúc: mỗi đèn/LED kết nối MQTT trực tiếp với cert/ACL riêng và bên mua yêu cầu broker-level per-device isolation. Khi đó A là biến thể triển khai, không phải đích mặc định.

### 6.1. Topic baseline C (Northbound — Cloud/Gateway)

| Loại | Topic | Hướng | QoS / Retain | Danh tính trong payload |
| :--- | :--- | :--- | :--- | :--- |
| Telemetry | `pccom/v1/{tenant}/{site}/{gateway_id}/telemetry` | Gateway → Cloud | QoS 1 / false | `device_type`, `device_id`, `asset_id`, metrics |
| Lệnh dim | `pccom/v1/{tenant}/{site}/{gateway_id}/cmd` | Cloud → Gateway | QoS 1 / false | `target` (asset/group/zone), `action`, `value`, `command_id`, `expires_at` |
| Ack/result | `pccom/v1/{tenant}/{site}/{gateway_id}/ack` | Gateway → Cloud | QoS 1 / false | `command_id`, `device_id`/`asset_id`, `status`, `observed_value` |
| Status/LWT | `pccom/v1/{tenant}/{site}/{gateway_id}/status` | Gateway → Cloud | QoS 1 / **true** (nếu bật retain) | `device_id`/`asset_id`, `status`; có thể gửi theo lô hoặc từng bản tin |
| Alerts | `pccom/v1/{tenant}/{site}/{gateway_id}/alerts` | Gateway → Cloud | QoS 1 / false | `device_id`, `alert_code`, `severity`, `related_correlation_id` |
| Receipt (tùy chọn) | `pccom/v1/{tenant}/{site}/{gateway_id}/receipt` | Cloud → Gateway | QoS 1 / false | `message_id`, `stored/quarantined`, `reason` |

> Nếu nhóm chốt cần route/lọc theo thiết bị ở northbound, thêm hậu tố `/{device_type}/{device_id}` sau category. Khi đó ACL gateway phải dùng wildcard `.../{category}/+/+`, và cần chấp nhận rằng gateway có thể ghi thay thiết bị sau nó.

Phase 1 đã triển khai builder/parser tại `src/iot_protocol/northbound_topics.py`, test tại `tests/test_northbound_topics.py`, và ACL `status`/`alerts` tại `acl.devices`/`acl.service`. Lab hiện vẫn giữ `retain_available false`, nên status northbound đang non-retained; chỉ bật retain sau khi chốt policy.

### 6.2. Topic baseline C (Southbound — Device/Gateway)

Giữ nguyên taxonomy IoT đã kiểm thử:

| Loại | Topic | Hướng | QoS / Retain |
| :--- | :--- | :--- | :--- |
| Telemetry | `telemetry/v1/{site}/{device_type}/{device_id}` | Thiết bị → Gateway | QoS 1 / false |
| Lệnh dim | `commands/v1/{site}/{device_type}/{device_id}/dim` | Gateway → Thiết bị | QoS 1 / false |
| Result | `commands/v1/{site}/{device_type}/{device_id}/dim/result` | Thiết bị → Gateway | QoS 1 / false |
| Status/LWT | `status/v1/{site}/{device_type}/{device_id}` | Thiết bị/Gateway | QoS 1 / **true** |
| Alerts | `alerts/v1/{site}/{device_type}/{device_id}` | Thiết bị/Gateway | QoS 1 / false |

### 6.3. ACL mẫu cho northbound (chỉ trong tài liệu)

```text
# Gateway lab: danh tính lấy từ cert mTLS, ví dụ gw-001
user gw-001
topic write pccom/v1/t1/s01/gw-001/telemetry
topic write pccom/v1/t1/s01/gw-001/ack
topic write pccom/v1/t1/s01/gw-001/status
topic write pccom/v1/t1/s01/gw-001/alerts
topic read  pccom/v1/t1/s01/gw-001/cmd
topic read  pccom/v1/t1/s01/gw-001/receipt

# Dispatcher/Cloud service
user dispatcher
topic read  pccom/v1/t1/s01/+/telemetry
topic read  pccom/v1/t1/s01/+/ack
topic read  pccom/v1/t1/s01/+/status
topic read  pccom/v1/t1/s01/+/alerts
topic write pccom/v1/t1/s01/+/cmd
topic write pccom/v1/t1/s01/+/receipt
```

Lưu ý:

- ACL trên chỉ minh họa; production phải tách theo tenant/site thực tế, không dùng literal `t1` cho mọi tenant.
- Nếu bật retained cho `status`, phải đổi `retain_available false` (`mosquitto.conf:3`) thành `true` và giới hạn retain đúng nhánh status.
- Bridge cần credential riêng; không dùng credential gateway cho bridge và không cấp cho thiết bị quyền ghi northbound.
- Southbound ACL giữ theo `deploy/mosquitto/aclfile.example` (có thể thêm tenant nếu broker southbound dùng chung).

### 6.4. C chuẩn hóa (C+) — đích dài hạn

Baseline C giữ nguyên taxonomy IoT ở southbound để không phá E2E hiện có. Đích dài hạn cần chuẩn hóa để tránh hai hợp đồng topic tiến hóa lệch nhau:

1. **Một canonical envelope dùng chung** cho cả hai lớp: `tenant_id`, `site_id`, `gateway_id`, `asset_id`, `device_id`, `message_id`, `schema_version`, `source_time`, `received_time`, `sequence`, `quality`, `command_id`, `status`, `reason`, `evidence`.
2. **Tenant-first ở cả hai lớp.** Nếu broker southbound dùng chung nhiều tenant, thêm tenant vào topic hoặc tách broker theo tenant/site; không để `site_id` đơn độc làm khóa toàn cục.
3. **Gateway là first-class asset và failure domain.** Gateway có LWT riêng; khi gateway offline, cloud đánh dấu các device con là `unknown/stale` trong ngân sách 30 giây, không tự động coi là `offline`.
4. **Per-device identity/authz tại gateway.** Gateway có registry thiết bị, kiểm tra target/command trước khi fan-out; cloud xác thực gateway bằng mTLS và không tin payload chưa xác thực. Nếu SEC 01 được hiểu là broker-level per-device ACL, phải nâng cấp cert/ACL trước khi go-live.
5. **Command lifecycle rõ ràng:** `cmd → ack → status`, `command_id` xuyên suốt, `expires_at`, chống replay, idempotency; broker PUBACK không phải bằng chứng thực thi.
6. **Spool/receipt:** gateway đệm telemetry tối thiểu 24h, giữ `sequence` theo thiết bị, đối soát duplicate sau reconnect; `receipt` là xác nhận lưu bền, không phải kết quả lệnh.
7. **Schema registry + contract test + dead letter:** version hóa topic/payload, từ chối bản tin sai schema/quá lớn/trái phép vào hàng lỗi được giám sát.
8. **Direct-device escape hatch:** thiết bị nào kết nối trực tiếp vẫn đi qua một “logical gateway” và được normalize về cùng northbound contract; không tạo hợp đồng cloud thứ hai.

Topic đích dài hạn (có thể giữ baseline C ở giai đoạn 1):

```text
# Edge zone: thiết bị ↔ gateway
pccom/edge/v1/{tenant}/{site}/{gateway_id}/{device_type}/{device_id}/{category}

# Cloud zone: gateway ↔ cloud
pccom/cloud/v1/{tenant}/{site}/{gateway_id}/{category}
```

Trong đó `category` gồm `telemetry`, `cmd`, `ack`, `status`, `alerts`; `receipt` là category tùy chọn ở cloud zone. Giai đoạn 1 giữ nguyên `telemetry/v1/...` và `pccom/v1/...`; bridge chịu trách nhiệm map hai profile.

### 6.5. Phase 2 đã triển khai trong repo

| Thành phần | File | Hành vi |
| :--- | :--- | :--- |
| Canonical envelope + khóa gateway | `src/iot_protocol/northbound_payload.py` | `build_envelope`, `parse_envelope`, `derive_gateway_key`, `command_target`, `normalize_ack_status` |
| Gateway bridge | `src/edge_gateway_bridge/bridge.py` | Mỗi gateway một MQTT client/LWT; subscribe telemetry/status/alerts/result southbound; publish telemetry/status/ack/alerts northbound; nhận `cmd` và fan-out |
| Northbound Mock Cloud | `src/backend/mock_cloud_service.py --northbound` | Subscribe `pccom/v1/{tenant}/+/+/{category}`; xác thực khóa gateway; gateway offline → device con `unknown` |
| Northbound Core API | `src/backend/core_api.py --northbound` | Gửi lệnh `cmd` qua gateway, giữ `command_id` xuyên suốt |
| Mapping cấu hình | `src/edge_simulator/config.py`, `config.example.json` | `northbound.tenant_id`, `sites`, `gateways`, `client_id_prefix`, `retain_status` |

Lệnh chạy kiến trúc C trong lab:

```powershell
# 1. Cloud northbound
python src/backend/mock_cloud_service.py --config config.json --northbound

# 2. Bridge (một hoặc nhiều gateway)
python src/edge_gateway_bridge/bridge.py --config config.json

# 3. Simulator southbound
python src/edge_simulator/virtual_lighting_network.py --config config.json

# 4. Core API northbound
python src/backend/core_api.py --northbound
```

Bằng chứng E2E ngày 16/11/2026 với `tests/fixtures/simulator.test.json`:

- `COMMAND_TX_NB` → `COMMAND_FWD` → `COMMAND RX` → `RESULT` → `ACK_FWD` → `ACK_RX` cùng `command_id`/`correlation_id`.
- `TELEMETRY_NB` nhận telemetry của `LGT_NODE_001`, `LGT_NODE_002`, `DSP_LED_001` qua `pccom/v1/t1/s01/gw-001/telemetry`.
- Crash bridge (`--crash-after`) → Cloud nhận `GATEWAY_STATUS gateway=gw-001 status=offline affected_devices=3`; không phát offline giả cho từng thiết bị.
- Bridge từ chối lệnh hết hạn/không hỗ trợ bằng `ack rejected`, giữ `command_id` để Cloud đối soát.
- `retain_status=false` giữ tương thích `retain_available false`; status không retained. Khi cần retained status phải bật đồng thời cấu hình broker và `northbound.retain_status`.

---

## 7. Việc cần chốt trước Sprint 3

**Đã chốt:** Phương án C (C chuẩn hóa) ngày 16/11/2026. Các mục dưới đây là chi tiết triển khai C, không phải lựa chọn lại A/B.

| # | Quyết định | Đề xuất mặc định | Người chốt |
| :---: | :--- | :--- | :--- |
| 1 | Kiến trúc kết nối: gateway-only hay mỗi đèn direct | Gateway gom cụm, một MQTT client/gateway | Chủ dự án + IoT |
| 2 | Tenant trong topic: slug `t1` hay UUID | Dùng đúng giá trị đang có trong cert/ACL; thống nhất kiểu dữ liệu | Chủ dự án |
| 3 | Device identity northbound: payload hay segment | Payload (`device_id`/`asset_id`) để giữ ACL gateway đơn giản | Chủ dự án + IoT |
| 4 | Status/LWT: gateway tổng hợp hay broker per-device | Gateway tổng hợp, timeout ≤ 30s; LWT broker chỉ cấp gateway | Chủ dự án |
| 5 | Retain cho status | Bật retain đúng nhánh `status`, tắt cho telemetry/command/ack/alerts | Chủ dự án |
| 6 | `ack` vs `receipt` | `ack` = kết quả lệnh; `receipt` = xác nhận lưu telemetry; giữ cả hai | Chủ dự án |
| 7 | Contract chuẩn: `contracts/` (slug + gateway_id) hay `docs/data_contracts/` (UUID, asset/device) | Chọn một bộ, mapping rõ ràng; không trộn UUID với slug trong cùng topic | Nhóm |
| 8 | Firmware legacy `pccom/lighting/...` | Chuyển qua bridge/southbound; không duy trì song song | IoT |
| 9 | Gateway failure domain | Gateway LWT; device con `unknown/stale` khi gateway mất; không flood offline từng thiết bị | Chủ dự án + IoT |
| 10 | Tenant ở southbound | Thêm tenant nếu broker dùng chung; hoặc tách broker theo tenant/site | Nhóm |
| 11 | Canonical envelope | Một bộ field dùng chung cho hai lớp; schema registry + contract test | Nhóm |
| 12 | Topic đích dài hạn | `pccom/edge/v1/...` và `pccom/cloud/v1/...`, tenant-first; baseline C là giai đoạn 1 | Nhóm |

---

## 8. Quyết định đã chốt và phần còn cần xác nhận nội bộ

**Đã chốt và đã có code:**

1. `gw-001`/`gw-002` là gateway gom nhiều đèn/LED; mỗi gateway một MQTT client/LWT.
2. `ack` là kết quả thực thi lệnh; `receipt` là xác nhận lưu/cách ly telemetry và để giai đoạn 3.
3. ACL `status`/`alerts` đã bổ sung ở Phase 1; LWT/status từng đèn do gateway tổng hợp từ southbound.
4. `tenant` dùng slug trong cấu hình (`t1` mặc định); map `sites`/`gateways` khai báo tường minh.
5. `device_type`/`device_id` nằm trong payload northbound; topic giữ cấp gateway.
6. Bridge do nhóm IoT làm tại `src/edge_gateway_bridge/`; SEC 01 hiện hiểu là gateway-level per-device authorization.
7. Chấp nhận offline từng đèn trễ tối đa 30 giây; device con chuyển `unknown` khi gateway mất.
8. Client simulator/bridge/cloud hỗ trợ mTLS (`broker.ca_cert`, `broker.client_cert`,
   `broker.client_key`); lab smoke ACL/TLS pass với `eclipse-mosquitto:2.0`. Bridge mTLS đã
   kiểm chứng status/LWT bằng cert `gw-001`; southbound qua bridge vẫn chờ chốt SEC 01.

**Còn cần xác nhận trước go-live:**

- Retain status: có bật `retain_available` và `northbound.retain_status` hay không.
- SEC 01 có bắt buộc broker-level per-device ACL hay chấp nhận gateway-level.
- Chọn canonical contract giữa `contracts/` và `docs/data_contracts/`.
- Phạm vi spool 24h, duplicate reconciliation và `receipt`.

---

## 9. Lộ trình triển khai C

| Giai đoạn | Nội dung | Điều kiện hoàn thành |
| :--- | :--- | :--- |
| **0. Chốt quyết định** | Chốt C, traceability RFP, baseline topic | Tài liệu này được review và chấp thuận |
| **1. Northbound contract** | Đã thêm `status`/`alerts` vào ACL gateway/dispatcher; định nghĩa builder/parser northbound; giữ nguyên southbound | Unit test topic pass; ACL đã cập nhật; smoke mTLS lab pass |
| **2. Bridge gateway** | **Đã triển khai** tại `src/edge_gateway_bridge/bridge.py`; map telemetry/status/alerts/result; nhận `cmd` và fan-out; phát `ack` | E2E simulator → bridge → mock cloud local + `broker.emqx.io` pass; command_id/ack khớp; bridge mTLS status/LWT pass |
| **3. Failure & offline** | Gateway LWT + device con `unknown` đã có; còn timeout per-device ≤30s, spool 24h, duplicate reconciliation, `receipt` optional | Test mất WAN 24h, gateway restart, mất điện, reconnect pass |
| **4. Canonical & scale** | Canonical envelope đã có (`northbound_payload.py`); còn schema registry, contract test, load 10.100 tài sản, dead letter | AT 01/02/03/05 và NFR 01 có bằng chứng |
| **5. Chuẩn hóa dài hạn** | Tenant-first cả hai lớp; `pccom/edge/v1` + `pccom/cloud/v1`; direct-device qua logical gateway | Không còn legacy `pccom/lighting/...`; tài liệu vận hành cập nhật |

**Nguyên tắc triển khai:** không đổi southbound trong giai đoạn 1; bridge là anti-corruption layer; mọi thay đổi topic phải có test và cập nhật ACL/đặc tả cùng lúc.

