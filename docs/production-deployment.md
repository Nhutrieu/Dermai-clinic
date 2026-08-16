# Triển khai production bằng Docker Compose

Tài liệu này mô tả cấu hình production chạy được trên **một Docker host**. Môi
trường local vẫn dùng riêng `docker-compose.yml`; production luôn ghép thêm
`docker-compose.production.yml`.

Yêu cầu Docker Compose **v2.24.4 trở lên** vì overlay dùng các merge tag
`!reset` và `!override` để bảo đảm cổng local không vô tình còn mở.

## 1. Khác biệt so với local

| Thành phần | Local | Production overlay |
|---|---|---|
| Frontend Nginx | host `3000` | loopback `${PUBLIC_HTTP_PORT}` (mặc định `3000`) |
| API Gateway | host `8080` | chỉ mạng Docker, frontend proxy `/api` và `/ai` |
| PostgreSQL | host `5432` | chỉ mạng database nội bộ |
| RabbitMQ management | host `15672` | không có host port |
| FastAPI/Swagger | host `8000` | chỉ mạng application nội bộ |
| Adminer | host `8081` | tắt mặc định; profile `maintenance`, không host port |
| Bí mật | có giá trị local mặc định | bắt buộc lấy từ `.env.production` |

Chỉ frontend được publish. Người dùng truy cập cùng một origin; Nginx chuyển
tiếp API, AI và WebSocket vào gateway nên không cần công khai gateway.
PostgreSQL, RabbitMQ và Redis dùng named volume thuộc project production, tách
khỏi dữ liệu local.

## 2. Chuẩn bị biến môi trường

```powershell
Copy-Item .env.production.example .env.production
```

Sửa `.env.production` và điền toàn bộ giá trị bắt buộc đang để rỗng. Compose sẽ
từ chối khởi động nếu còn thiếu. Có thể tạo chuỗi ngẫu nhiên bằng công cụ quản lý
secret của nền tảng. Không ghi secret vào file
Compose, tài liệu, ảnh chụp, log hoặc Git. Ba giá trị tối thiểu bắt buộc là mật
khẩu PostgreSQL, JWT secret và service token; RabbitMQ cũng dùng tài khoản riêng.

`PUBLIC_ORIGIN` phải là origin HTTPS thật, ví dụ `https://clinic.example.com`,
không có path và không có dấu `/` cuối. Khi dùng reverse proxy TLS trên cùng máy,
giữ `PUBLIC_BIND_ADDRESS=127.0.0.1`; reverse proxy chuyển toàn bộ request HTTP,
API và WebSocket tới `127.0.0.1:${PUBLIC_HTTP_PORT}`.
Chỉ dùng `0.0.0.0` khi một network edge tin cậy chặn truy cập trực tiếp và luôn
ghi đè `X-Forwarded-Proto`; Nginx ứng dụng không tự xác thực header này.

Email mặc định bị tắt (`SMTP_AUTH=false`). Khi cần OTP/email thật, phải cấu hình
đủ `SMTP_USERNAME`, `SMTP_PASSWORD`, `MAIL_FROM`, bật `SMTP_AUTH=true` và
`SMTP_STARTTLS=true`, rồi chạy một lượt gửi thử trước khi mở hệ thống.

AI cần có checkpoint tại `${AI_MODEL_DIR}/best_model.pth` và dữ liệu RAG tại
`${AI_RAG_INDEX_DIR}`. Hai thư mục được mount read-only; source Python chạy từ
image thay vì bind mount như local.

## 3. Kiểm tra trước khi chạy

```powershell
docker compose `
  --env-file .env.production `
  -f docker-compose.yml `
  -f docker-compose.production.yml `
  config --quiet
```

Lệnh phải thất bại nếu thiếu secret bắt buộc. Không chạy `docker compose config`
không có `--quiet` trong terminal được ghi log hoặc ảnh báo cáo: biến môi trường
của shell có độ ưu tiên cao và bản render đầy đủ có thể chứa secret.

## 4. Build và khởi động

```powershell
docker compose `
  --env-file .env.production `
  -f docker-compose.yml `
  -f docker-compose.production.yml `
  up -d --build --wait
```

`--wait` dựa trên healthcheck hiện có của PostgreSQL, RabbitMQ, Redis, các service
Spring, FastAPI, gateway và frontend. Kiểm tra sau triển khai:

```powershell
docker compose `
  --env-file .env.production `
  -f docker-compose.yml `
  -f docker-compose.production.yml `
  ps

Invoke-WebRequest "http://127.0.0.1:3000/health"
```

Thay `3000` trong lệnh health nếu đã cấu hình `PUBLIC_HTTP_PORT` khác. Tùy chọn
`--env-file` chỉ cấp biến cho Compose, không tự gán `$env:PUBLIC_HTTP_PORT` vào
phiên PowerShell hiện tại.

Không dùng `down -v` trong production vì tùy chọn `-v` xóa volume PostgreSQL.

## 5. TLS và giới hạn phạm vi

Overlay không tự cấp chứng chỉ TLS vì domain và nhà cung cấp của môi trường triển
khai chưa được chốt. Trước khi mở Internet, đặt Caddy, Nginx, load balancer hoặc
dịch vụ cloud ở phía trước frontend và bắt buộc HTTPS/WSS. Chỉ mở `80/443` ở
firewall; không mở `5432`, `8000`, `8080`, `8081` hoặc `15672`.

Để bảo trì database, ưu tiên `docker compose ... exec postgres psql` qua SSH.
Nếu bắt buộc dùng Adminer, tạo một override tạm chỉ bind `127.0.0.1:8081:8080`,
mở SSH tunnel tới cổng đó rồi xóa override sau phiên; không publish Adminer ra
`0.0.0.0`.

Đây là cấu hình single-host phù hợp đồ án và bản demo có kiểm soát. Backup ngoài
máy, restore drill, log tập trung, giám sát/cảnh báo và secret manager vẫn là các
hạng mục vận hành phải hoàn tất trước khi gọi hệ thống là production-ready ở quy
mô phòng khám thực tế.
