# Playwright E2E

Bộ test này chạy trên hệ thống DermAI thật: không intercept API và không tạo dữ liệu nghiệp vụ giả.
Các test hiện có là:

- `E2E-BOOK-001`: Patient đăng nhập, chọn bác sĩ/ngày/slot, giữ chỗ và xác nhận lịch.
- `E2E-BOOK-002`: hai Patient độc lập cùng chọn một slot; kết quả bắt buộc là một `201`, một `409` và chỉ một lịch được tạo.
- `E2E-FLOW-001`: Patient đặt lịch hôm nay → lễ tân xác nhận/check-in → bác sĩ ký hồ sơ và hoàn tất → Patient gửi review.
- `E2E-AI-001`: Patient tải ảnh thật, chạy model, lưu ảnh/kết quả và bật quyền chia sẻ khi đặt lịch.
- `E2E-CHAT-001`: trợ lý chuyển yêu cầu thao tác sang lễ tân, lễ tân nhận xử lý, trả lời và hoàn tất handoff.

Test tự hủy rồi ẩn lịch, xóa assessment hoặc nhả hold trong `finally` khi API cho phép. Hồ sơ đã ký, review, audit và transcript hỗ trợ không có API xóa vật lý; vì vậy chỉ chạy lifecycle trên database local/staging dùng cho kiểm thử, không chạy trên production.

## Chuẩn bị

1. Chạy đầy đủ Docker Compose và kiểm tra web ở `http://localhost:3000`.
2. Bảo đảm có ít nhất một bác sĩ đang hoạt động, có lịch làm việc và slot trống trong 60 ngày tới.
3. Tạo hai Patient đã xác minh email, đã hoàn thiện hồ sơ, dùng hai identity khác nhau và chưa đạt giới hạn ba lịch sắp tới.
4. Tạo một Receptionist đang hoạt động và một Doctor đang hoạt động. Doctor E2E cần có slot còn trống trong **hôm nay** để test check-in/lượt khám chạy được.
5. Chuẩn bị một ảnh JPEG/PNG/WebP thật, không quá 3 MB, để test AI.
6. Cài Chromium một lần:

```powershell
Set-Location frontend
npm install
npx.cmd playwright install chromium
```

## Chạy test

Thiết lập credential trong chính phiên terminal, không ghi mật khẩu vào Git:

```powershell
$env:E2E_PATIENT_1_EMAIL = "patient-e2e-1@example.test"
$env:E2E_PATIENT_1_PASSWORD = "replace-with-real-password"
$env:E2E_PATIENT_2_EMAIL = "patient-e2e-2@example.test"
$env:E2E_PATIENT_2_PASSWORD = "replace-with-real-password"
$env:E2E_RECEPTIONIST_EMAIL = "reception-e2e@example.test"
$env:E2E_RECEPTIONIST_PASSWORD = "replace-with-real-password"
$env:E2E_DOCTOR_EMAIL = "doctor-e2e@example.test"
$env:E2E_DOCTOR_PASSWORD = "replace-with-real-password"
$env:E2E_AI_IMAGE_PATH = "D:\e2e-data\skin-sample.jpg"

# Tùy chọn; mặc định là http://localhost:3000 và tìm slot trong 60 ngày.
$env:E2E_BASE_URL = "http://localhost:3000"
$env:E2E_SEARCH_DAYS = "60"

npm run test:e2e
```

Mặc định video chỉ được giữ khi test lỗi. Khi cần quay video cho bộ bằng chứng bảo vệ, đặt biến sau trước khi chạy:

```powershell
$env:E2E_VIDEO = "on"
npm run test:e2e
```

Nếu thiếu credential/ảnh, web/backend/model chưa chạy, tài khoản đã đạt giới hạn lịch hoặc không có slot phù hợp, test được đánh dấu `skipped` kèm nguyên nhân; trường hợp phản hồi nghiệp vụ sai vẫn là `failed`. Riêng `E2E-FLOW-001` dùng đúng Doctor của `E2E_DOCTOR_EMAIL` và chỉ chạy khi Doctor đó có một slot tương lai trong ngày hiện tại theo múi giờ `Asia/Ho_Chi_Minh`.

Kết quả máy đọc được nằm tại `test-results/e2e-junit.xml` và `test-results/e2e-results.json`. Báo cáo HTML nằm tại `playwright-report/`; mở bằng `npm run test:e2e:report`. Screenshot thành công và JSON bằng chứng được đính kèm trong report. Khi lỗi, Playwright giữ thêm trace, screenshot và video. Các artifact có thể chứa thông tin tài khoản/dữ liệu demo, vì vậy không commit hoặc chia sẻ công khai.
