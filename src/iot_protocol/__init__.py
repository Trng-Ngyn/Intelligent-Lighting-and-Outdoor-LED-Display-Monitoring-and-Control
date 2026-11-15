"""Gói dùng chung cho giao thức MQTT 5 của hệ thống PCCOM.

Gói này chứa các quy tắc thuần Python (không phụ thuộc paho) để:
- Ghép và phân tích topic theo taxonomy phiên bản v1.
- Tạo chuỗi canonical, ký và xác thực HMAC-SHA256.
- Kiểm tra User Properties và chống replay.

Xem đặc tả đầy đủ tại:
docs/specifications/MQTT5_COMMUNICATION_PROTOCOL.md
"""
