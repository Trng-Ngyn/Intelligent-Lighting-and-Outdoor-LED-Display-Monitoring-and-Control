# S7 — Mẫu báo cáo soak 4h (CHƯA CÓ SỐ ĐO)

> **Trạng thái: MẪU — không phải bằng chứng.** Mọi ô `___` phải được điền bằng
> output thật từ bo ESP32-WROOM-32. Không copy số từ phần host-side self-test.
> Không commit log serial/PEM/secret; chỉ commit bảng tổng hợp đã điền.

## Thông tin chạy

| Trường | Giá trị |
| :-- | :-- |
| Board | ESP32-WROOM-32, flash 4MB |
| Firmware | profile `esp32_dev`, build sau refactor device-key |
| Broker | lab 8885 (`mqtt.dev.pccom.test`) hoặc Staging (ghi rõ) |
| Bắt đầu (UTC) | `___` |
| Kết thúc (UTC) | `___` |
| Thời gian thực tế | `___` phút (mục tiêu 240) |
| Cổng UART / log | `___` (log lưu ngoài repo) |

## Lệnh đã chạy

```powershell
# 1. Collector (chạy 240 phút, master secret chỉ đọc trên host)
& '.\.venv\Scripts\python.exe' tools\soak_collector.py `
    --duration-min 240 --secret-file C:\secure\master.secret `
    --out C:\secure\soak_result.json

# 2. Log serial song song để đối chiếu heap/stack
& '..\..\.venv\Scripts\python.exe' -m platformio device monitor -e esp32_dev |
    Tee-Object -FilePath 'C:\Users\DELL\AppData\Local\Temp\opencode\firmware_soak.log'
```

`soak_result.json` chỉ chứa số liệu tổng hợp; không chứa payload hay secret.

## Kết quả telemetry (từ collector)

| Chỉ số | Kỳ vọng | Thực đo |
| :-- | :-- | :-- |
| Bản tin thu được | ≈1440 (10s × 240ph) | `___` |
| Tỷ lệ phủ | ≥98% | `___ %` |
| `schema_ok` | = bản tin thu được | `___` |
| `signature_ok` | = bản tin thu được | `___` |
| `sequence_ok` | = bản tin thu được, không gap/replay | `___` |
| `qos1_ok` | = bản tin thu được | `___` |
| `telemetry_non_retained` | = bản tin thu được | `___` |
| `interval_ok` (|Δ−10s| ≤ 2s) | ≥95% | `___` |
| `status_retained` online | ≥1 | `___` |
| LWT `offline` (cắt điện có chủ đích) | 1, ≤30s từ bản tin cuối | `___` |
| `error_counts` | `{}` | `___` |

## Kết quả heap/stack (từ log serial, mỗi 60s)

| Chỉ số | Kỳ vọng | Thực đo |
| :-- | :-- | :-- |
| `free_heap` cuối | ≥ 80% giá trị đầu | `___ → ___` byte |
| `min_free_heap` | > 0, không tiến về 0 | `___` byte |
| `largest_block` | không suy về 0 | `___` byte |
| `stack_min` net / ingest / tele / mqtt | > 0 (không tràn) | `___ / ___ / ___ / ___` word |
| `reconnect` / `publish_fail` / `queue_overflow` | 0 (hoặc có giải thích) | `___ / ___ / ___` |
| TWDT reset / reboot / panic | 0 | `___` |
| Số task ứng dụng | đúng 3 | `___` |

## Kết luận

- [ ] Đạt DoD S7 (điền bằng chứng ở trên trước khi tick).
- [ ] Không đạt — ghi rõ nguyên nhân: `___`.

Part cần bo/broker thật được liệt kê trong
`docs/test_reports/FIRMWARE_AUDIT_S0_S7.md`; self-test host-side của collector
**không** thay thế bảng này.
