# Ma Trận Truy Vết Yêu Cầu (Requirements Traceability Matrix - RTM)
**Chịu trách nhiệm:** Phuoc Nguyen (`daiphuoc1914@gmail.com`) - QA Engineering Developer  
**Hồ sơ kỹ thuật:** Mục 8 (Acceptance tests and measurement) & Gate G0

---

## 1. Ma trận truy vết Sprint 1 (Cổng Gate G0)
| Mã Yêu Cầu | Tên Yêu Cầu | Mã Test Case Nghiệm Thu | Mã Nguồn / Bằng Chứng | Trạng thái G0 |
| :---: | :--- | :---: | :--- | :---: |
| **LGT 01** | Quản lý Asset ID & Thông số định danh | **AT 01** | `src/firmware_esp32/include/config.h` | PASS (Bench Test) |
| **LGT 02** | Lệnh bật/tắt & Dimming an toàn | **AT 02** | `src/firmware_esp32/src/main.cpp` | PASS (First Slice) |
| **LGT 05** | Đo lường điện áp, dòng điện, công suất | **AT 03** | `src/firmware_esp32/include/data_contract.h` | PASS (Telemetry) |
| **DSP 04** | Lưu đệm danh sách phát khi mất mạng | **AT 04, AT 05** | `src/backend/mock_cloud_service.py` | PASS (Offline Mode) |
| **SEC 01** | Bảo mật xác thực thiết bị và định danh | **AT 08** | Client ID, Token phân quyền MQTT 5 | PASS (Auth Verified) |
