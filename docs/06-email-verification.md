# Xác minh email, Google Login và Gmail SMTP

> Cập nhật theo Auth Service ngày 11/08/2026.

Tài khoản bệnh nhân đăng ký bằng email/mật khẩu phải xác minh OTP trước khi đăng
nhập. OTP gồm 6 số, hết hạn sau 5 phút, tối đa 5 lần thử và chỉ được gửi lại sau
60 giây. Tài khoản Google được xem là đã xác minh bởi Google Identity Services.

| Luồng | Endpoint |
|---|---|
| Gửi lại OTP xác minh | `POST /api/v1/auth/verification/send` |
| Xác nhận OTP | `POST /api/v1/auth/verification/confirm` |
| Quên mật khẩu | `POST /api/v1/auth/forgot-password` |
| Đặt lại mật khẩu | `POST /api/v1/auth/reset-password` |
| Đọc cấu hình Google công khai | `GET /api/v1/auth/google/config` |
| Đăng nhập bằng Google credential | `POST /api/v1/auth/google` |

## Cấu hình Gmail gửi email thật

1. Bật xác minh hai bước cho tài khoản Google.
2. Tạo một App Password riêng, đặt tên gợi nhớ như `DermAI Clinic`.
3. Tại thư mục dự án, chạy:

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\configure-gmail-smtp.ps1"
```

Script yêu cầu nhập Gmail và App Password ngay trên máy. App Password được nhập ẩn, chỉ lưu trong `.env`, không được ghi vào Git hoặc in ra terminal.

## Cấu hình môi trường

Các biến được sử dụng gồm `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`,
`SMTP_PASSWORD`, `SMTP_AUTH`, `SMTP_STARTTLS` và `MAIL_FROM`. Google Login dùng
client ID trong biến cấu hình tương ứng của Auth Service; client secret không cần
đưa xuống frontend. Hệ thống dùng Gmail SMTP cho OTP và email trạng thái lịch
khám; MailHog đã được loại khỏi môi trường chạy.

## Kiểm tra và an toàn

- Không commit `.env`, App Password, refresh token hoặc Google credential.
- Thử cả OTP đúng, sai, hết hạn, vượt số lần thử và gửi lại quá sớm.
- Response quên mật khẩu không được tiết lộ email có tồn tại hay không.
- Rate limit các endpoint gửi OTP, đăng nhập và quên mật khẩu trước khi public.
- Khi App Password bị lộ hoặc không còn sử dụng, thu hồi ngay trong Google
  Account và tạo mã mới.
- Access token hết hạn sau 15 phút; frontend tự refresh một lần. Refresh token
  hết hạn sau 14 ngày, được rotate khi dùng và thu hồi khi logout.
