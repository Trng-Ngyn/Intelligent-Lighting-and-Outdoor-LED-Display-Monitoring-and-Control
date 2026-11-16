"""Gói dùng chung cho giao thức MQTT 5 của hệ thống PCCOM.

Gói này chứa các quy tắc thuần Python (không phụ thuộc paho) để:
- Ghép và phân tích topic southbound theo taxonomy phiên bản v1.
- Ghép và phân tích topic northbound theo Phương án C (`pccom/v1/...`).
- Tạo canonical envelope và khóa HMAC cấp gateway cho northbound.
- Tạo chuỗi canonical, ký và xác thực HMAC-SHA256.
- Kiểm tra User Properties và chống replay.

Xem đặc tả đầy đủ tại:
docs/specifications/MQTT5_COMMUNICATION_PROTOCOL.md
"""
