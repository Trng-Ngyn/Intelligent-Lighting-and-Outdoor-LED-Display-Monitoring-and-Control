# PCCOM · Mẫu cấu hình Technical Lead & DevOps

## Chạy thử MQTT 5 và API mTLS

Chuẩn bị Linux hoặc WSL2, Docker với Compose v2, OpenSSL 3 và curl. Giải nén
trên hệ thống tệp Linux (ví dụ thư mục cá nhân trong WSL) để giữ quyền 0600.
Cổng 8883 và 8443 chỉ bind ở loopback. Dùng tài nguyên chạy thử và dữ liệu giả lập.
Mở `contracts/README.md` để xem schema JSON và dữ liệu mẫu cho telemetry,
receipt, command, ACK và manifest.

```bash
bash lab/generate-pki.sh
docker compose --env-file lab/compose.env -f lab/compose.yml up -d
bash lab/smoke.sh
docker compose --env-file lab/compose.env -f lab/compose.yml down -v
```

`generate-pki.sh` tạo CA server, CA gateway và CA dịch vụ cùng các chứng chỉ
ngắn hạn. Các CA này chỉ dành cho lab. File sinh trong `lab/generated/` chứa
khóa riêng và được bỏ qua khi commit. Nếu tạo lại, hãy dừng Compose và chuyển
thư mục `lab/generated/` ra một vị trí kiểm thử mới trước khi chạy lại.

`lab/smoke.sh` kiểm tra API có serial đã đăng ký và MQTT 5 phân quyền topic.
Listener MQTT 8883 dành cho thiết bị. Listener 8884 dành cho dịch vụ và chỉ
truy cập trong mạng Compose. API chỉ có `GET /v1/edge/health` mô phỏng.
Các phần kiểm chữ ký lệnh, nhật ký thực thi, chấp thuận theo tenant/site,
thu hồi phiên đang chạy và adapter phần cứng được đặc tả trong SAD để tích hợp.

## Phạm vi đã kiểm tra

Cấu hình MQTT và NGINX đã được chạy cục bộ với Mosquitto 2.0.21,
NGINX 1.26.3 và OpenSSL 3.5.7. MQTT 5 cho phép gateway ghi vào topic được cấp
và dispatcher phát lệnh. Broker chặn ghi vào site khác, chặn gateway ghi lệnh
và giữ phiên của gw-002 khi gw-001 tự gửi client ID trùng. API cho phép
certificate đã đăng ký. Các trường hợp sai CA, sai hostname, thiếu cert
và cert đã thu hồi bị từ chối tại đầu nối. Với API, cert đúng CA nhưng chưa
đăng ký cũng bị từ chối.

Chạy lại `lab/smoke.sh` với phiên bản ảnh Compose đã khóa digest trong Dev.
Dùng ma trận kèm theo để kiểm tra đầy đủ quyền subscribe, thu hồi phiên đang mở,
xác thực Registry trên broker, chữ ký lệnh và fallback trên Staging.

## Kết nối GitHub Actions

1. Tạo hai GitHub Environments đúng tên `dev` và `staging`. Giới hạn nhánh
   `develop` vào Dev và `release/staging` vào Staging. Bảo vệ hai nhánh và
   yêu cầu review các tệp workflow, cấu hình IAM, bản phát hành.
2. Yêu cầu người khác duyệt triển khai Staging và bật Prevent self-review
   khi gói GitHub hỗ trợ. Nếu repo private chưa có Required reviewers, dùng
   phê duyệt tại pull request để cập nhật nhánh `release/staging` được bảo vệ
   hoặc cổng phê duyệt đã được dự án chấp nhận.
3. Trong mỗi tài khoản AWS, thêm GitHub OIDC provider và tạo một deployment
   role riêng. Điền mẫu `ops/iam/oidc-trust.json` bằng `sub` chính xác
   của repo và môi trường thực tế. Repo có thể dùng định dạng có ID bất biến
   hoặc cấu hình tùy chỉnh. Kiểm tra claim thực tế và giữ điều kiện `StringEquals`.
   Điền `ops/iam/ecs-deploy.json` theo service và family của từng môi trường.
4. Đặt các GitHub Environment Variables `AWS_ACCOUNT_ID`, `AWS_REGION`,
   `AWS_ROLE_ARN`, `ECS_CLUSTER` và `ECS_SERVICE`. Đây là cấu hình triển khai.
   Cấp quyền đọc secret cho task role của ứng dụng theo ARN dưới
   `/pccom/dev/` hoặc `/pccom/staging/`. Đặt secret trong AWS Secrets Manager.
5. Đăng ký ECS task definition từ quy trình build đã duyệt, dùng image theo
   digest và đúng family `pccom-core-dev` hoặc `pccom-core-staging`. Đặt ARN đã
   duyệt vào `ops/releases/<environment>.task-arn`. Thay các giá trị mẫu trước
   khi triển khai. Cấu hình ECS rolling deployment, circuit breaker có rollback
   và health check. Job deploy cập nhật một service có sẵn và xác nhận revision
   PRIMARY đã hoàn tất, kể cả khi ECS tự quay về bản cũ.
6. Dev chạy sau push vào `develop`. Staging chạy bằng Run workflow với nhánh
   `release/staging` và target `staging`. Kiểm tra API, MQTT, DB read/write và
   audit trong môi trường đích theo kế hoạch QA. Thu lại run ID và task ARN.
   Để rollback chủ động, đưa ARN trước đó đã duyệt vào file môi trường tương ứng
   qua nhánh được bảo vệ rồi chạy lại workflow. Đảm bảo schema tương thích.

`lab-ci.yml` chạy kiểm thử Compose, độc lập với quyền truy cập Cloud. Trước khi
dùng trong Staging, cập nhật image/tag thành digest đã rà soát và ghi phiên bản
OpenSSL, broker, proxy, AWS CLI vào bằng chứng chạy. Gói mẫu chưa mang thông tin
tài khoản, cấu hình thiết bị thật hoặc quyền triển khai.

- [Eclipse Mosquitto](https://mosquitto.org/man/mosquitto-conf-5.html)
- [NGINX SSL module](https://nginx.org/en/docs/http/ngx_http_ssl_module.html)
- [GitHub Actions OIDC](https://docs.github.com/en/actions/reference/security/oidc)
- [AWS IAM role cho GitHub OIDC](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-idp_oidc.html)
