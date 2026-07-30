# Xác minh email và Gmail SMTP

Tài khoản bệnh nhân đăng ký bằng email/mật khẩu phải xác minh OTP trước khi đăng nhập. OTP gồm 6 số, hết hạn sau 5 phút, tối đa 5 lần thử và chỉ được gửi lại sau 60 giây. Tài khoản Google được xem là đã xác minh bởi Google Identity Services.

## Cấu hình Gmail gửi email thật

1. Bật xác minh hai bước cho tài khoản Google.
2. Tạo một App Password riêng, đặt tên gợi nhớ như `DermAI Clinic`.
3. Tại thư mục dự án, chạy:

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\configure-gmail-smtp.ps1"
```

Script yêu cầu nhập Gmail và App Password ngay trên máy. App Password được nhập ẩn, chỉ lưu trong `.env`, không được ghi vào Git hoặc in ra terminal.

## Cấu hình môi trường

Các biến được sử dụng gồm `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_AUTH`, `SMTP_STARTTLS` và `MAIL_FROM`. Hệ thống dùng Gmail SMTP cho cả OTP xác minh và email trạng thái lịch khám; MailHog đã được loại bỏ khỏi môi trường chạy.

Không commit `.env`. Khi App Password bị lộ hoặc không còn sử dụng, cần thu hồi ngay trong Google Account và tạo mã mới.
