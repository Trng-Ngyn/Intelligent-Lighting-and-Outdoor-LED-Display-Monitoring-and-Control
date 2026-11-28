# S0 — Khử blocker lab trước khi lên firmware thật

Ngày: 2026-11-27. Phạm vi: chỉ lab mTLS/MQTT 5. **Không** chạy `espefuse burn`,
không nạp firmware, không dùng profile `secure`.

## Các blocker đã sửa

| File | Vấn đề | Xử lý |
| :-- | :-- | :-- |
| `acl.devices` | Conflict marker `<<<<<<< HEAD`/`=======`/`>>>>>>> main`, user `gw-001` lặp | Gộp thành một user `gw-001`; giữ `bridge-s01`, `bridge-s02`, `bridge-gw-001`, `gw-002` |
| `docker-compose.lab.yml` | Chưa publish field listener | Publish thêm `127.0.0.1:8885:8885` |
| `generate-pki.sh` | Cert broker chỉ có SAN DNS; field bridge cert ghi đè `bridge-s01.crt` | Thêm `DNS:localhost,IP:127.0.0.1`; field bridge đổi thành `test-clients/field-bridge-s01.*` (vẫn CN `bridge-s01`) |
| `lab/` (mới) | Compose/Dockerfile trỏ `retain_policy.c`, `requirements.txt`, `check_alignment.py` nhưng thư mục không tồn tại | Tạo đủ 5 file; plugin v5 chỉ giữ `retain` trên nhánh `status` |
| `smoke.sh` | Dùng `compose.yml` không tồn tại; chưa test 8885 | Đổi sang `docker-compose.lab.yml`; thêm test ACL 8885 |
| `README.md` | Hướng dẫn dùng `lab/...` sai layout | Cập nhật lệnh, mô tả 3 listener và plugin retain |

## Lệnh kiểm chứng

```bash
bash -n generate-pki.sh smoke.sh
python -m py_compile lab/check_alignment.py
docker compose --env-file compose.env -f docker-compose.lab.yml config --quiet
bash generate-pki.sh
docker compose --env-file compose.env -f docker-compose.lab.yml up -d --build
bash smoke.sh
```

Kết quả: tất cả lệnh trên trả về 0. `smoke.sh` in:

- `API: authorized cert; unknown serial, missing/revoked cert, wrong CA and hostname checked.`
- `MQTT 5: valid publish, command service, bridge ACL, cross-site denial and rejected CA/CRL checked.`
- `Field 8885: per-device cert, retained status, cross-site denial and command write checked.`
- `TOPICS: builder khớp telemetry/status/alerts/result`
- `RETAIN: telemetry bị đổi thành non-retained`
- `RETAIN: status được giữ lại`
- `LWT: offline retained sau 0.05–1.00s (Will Delay Interval = 0)`
- `ALIGNMENT: PASS`

Broker log xác nhận 3 listener 8883/8884/8885 mở, plugin `pccom-retain.so` nạp
thành công. LWT được đo từ thời điểm đóng socket của clientWill tới lúc observer
nhận `offline`, không suy từ keepalive.

## TLS 1.3

```bash
openssl s_client -connect 127.0.0.1:8885 -servername mqtt.dev.pccom.test \
  -tls1_3 -CAfile generated/test-clients/server-ca.crt \
  -cert generated/test-clients/dev_SITE_01_LGT_NODE_001.crt \
  -key generated/test-clients/dev_SITE_01_LGT_NODE_001.key -brief
```

Kết quả: `Protocol version: TLSv1.3`, `Ciphersuite: TLS_AES_256_GCM_SHA384`,
`Verification: OK`.

## Ghi chú

- Cảnh báo `Found orphan containers ([pccom-mosquitto])` đến từ project Compose
  dev cũ (`docker-compose.dev.yml`), không ảnh hưởng lab.
- `generated/`, `compose.env` và mọi `*.key/*.crt` nằm ngoài git (đã có trong
  `.gitignore`). Không có secret nào được in ra log.
