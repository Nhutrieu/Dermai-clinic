# Playwright E2E

Bộ test chạy trên các dịch vụ DermAI thật, không intercept API. Môi trường cô lập dùng tài khoản/dữ liệu tổng hợp và PayOS giả lập; AI/RAG nạp thật. Các kết quả nghiệp vụ được kiểm tra từ API và giao diện thực thi.
Các test hiện có là:

- `E2E-BOOK-001`: Patient đăng nhập, chọn bác sĩ/ngày/slot, giữ chỗ và xác nhận lịch.
- `E2E-BOOK-002`: hai Patient độc lập cùng chọn một slot; kết quả bắt buộc là một `201`, một `409` và chỉ một lịch được tạo.
- `E2E-FLOW-001`: Patient đặt lịch hôm nay → lễ tân xác nhận/check-in → bác sĩ ký hồ sơ và hoàn tất → Patient gửi review.
- `E2E-AI-001`: Patient tải ảnh kiểm thử, chạy model thật, lưu ảnh/kết quả, bật quyền chia sẻ và mở biểu mẫu đặt lịch có ngữ cảnh AI.
- `E2E-CHAT-001`: trợ lý chuyển yêu cầu thao tác sang lễ tân, lễ tân nhận xử lý, trả lời và hoàn tất handoff.
- `E2E-PROPOSAL-001`: lễ tân tạo hai đề nghị lịch; Patient chấp nhận một đề nghị và từ chối đề nghị còn lại trên giao diện.
- `E2E-PAY-001`: hủy tại trang trả về thanh toán; giao dịch và lịch chuyển sang hủy, slot được giải phóng.
- `E2E-PAY-002`: thanh toán cọc, hủy lịch, yêu cầu hoàn cọc; lễ tân xác nhận hoàn tiền mặt.
- `E2E-BILL-001`: từ fixture ca khám đã cọc trong ngày, lễ tân xác nhận/check-in → bác sĩ khám/kê đơn/xác nhận dịch vụ → hóa đơn trừ đúng cọc → thu tiền mặt và tiền thối → cấp thuốc, giảm đúng tồn kho. Kiểm tra hóa đơn chưa trả không vào hàng đợi Dược, thu thiếu bị từ chối và không xuất lặp. Kịch bản này không xác nhận bước đặt lịch/cọc trên trình duyệt; bước đó thuộc `E2E-BOOK-001` và `E2E-FLOW-001`.

`E2E-FLOW-001` hiện kiểm tra cả hóa đơn và cấp thuốc, ngoài hồ sơ, đơn thuốc và review.

## Chạy trên database sạch (khuyến nghị)

Từ thư mục gốc, sau khi bật Docker Desktop và cài Chromium:

```powershell
powershell -ExecutionPolicy Bypass -File tests/run-isolated-e2e.ps1
```

Runner tạo project/volume riêng, build mã hiện tại, chờ healthcheck, tạo tài khoản tổng hợp với mật khẩu ngẫu nhiên và chạy đủ 9 kịch bản. SMTP trỏ loopback; PayOS dùng `FakePayOSGateway`, không chuyển tiền thật. AI vẫn nạp model/RAG thật. File/hash của checkpoint phải có trên máy.

Fixture bác sĩ làm mỗi ngày, `CLINIC_WEEKLY_CLOSURE_DAY=NONE` chỉ trong stack test. Có thêm fixture ca khám đã cọc của **Patient 2** cho `E2E-BILL-001`, truyền qua `E2E_BILLING_APPOINTMENT_ID`; fixture này cho phép kiểm tra hóa đơn/kho khi đã hết slot đặt lịch trong ngày và không chặn quy tắc cùng bác sĩ/cùng ngày của **Patient 1** trong FLOW. `E2E-FLOW-001` vẫn yêu cầu slot tương lai trong hôm nay và sẽ **SKIP** nếu không còn slot; không tính kịch bản đó PASS từ kết quả BILL.

Artifact, revision có `workingTreeDirty`, hash mã nguồn, JUnit/JSON, ảnh/video và report nằm tại `frontend/e2e-artifacts/<project>/`. Runner trả mã `2` khi Playwright không lỗi nhưng còn SKIP; chỉ mã `0` mới đủ gate. Mặc định runner dọn container/volume riêng và file secret sau khi chạy. Dùng `-KeepStack` để giữ môi trường phục vụ điều tra; cổng web là `http://localhost:53000`.

Test tự hủy rồi ẩn lịch, xóa assessment hoặc nhả hold trong `finally` khi API cho phép. Hồ sơ đã ký, review, audit và transcript hỗ trợ không có API xóa vật lý; vì vậy chỉ chạy lifecycle trên database local/staging dùng cho kiểm thử, không chạy trên production.

## Chuẩn bị

1. Chạy đầy đủ Docker Compose và kiểm tra web ở `http://localhost:3000`.
2. Bảo đảm có ít nhất một bác sĩ đang hoạt động, có lịch làm việc và slot trống trong 60 ngày tới.
3. Tạo hai Patient đã xác minh email, đã hoàn thiện hồ sơ, dùng hai identity khác nhau và chưa đạt giới hạn ba lịch sắp tới.
4. Tạo một Receptionist, một Doctor và một Pharmacist đang hoạt động. Doctor E2E cần có slot còn trống trong **hôm nay** để test đặt lịch/check-in/lượt khám chạy được.
5. Bộ test đã có sẵn ảnh synthetic `e2e/fixtures/synthetic-eczema-e2e.png` và không chứa dữ liệu bệnh nhân. Có thể thay bằng ảnh JPEG/PNG/WebP khác, không quá 3 MB, qua `E2E_AI_IMAGE_PATH`.
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
$env:E2E_PHARMACIST_EMAIL = "pharmacist-e2e@example.test"
$env:E2E_PHARMACIST_PASSWORD = "replace-with-real-password"
# Tùy chọn: bỏ dòng này để dùng fixture synthetic có sẵn trong repository.
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

Kết quả máy đọc được nằm tại `test-results/e2e-junit.xml` và `test-results/e2e-results.json`. Báo cáo HTML nằm tại `playwright-report/`; mở bằng `npm run test:e2e:report`. Có thể đặt `E2E_ARTIFACT_ROOT` để lưu toàn bộ kết quả sang thư mục khác khi cần giữ nhiều lượt chạy. Screenshot thành công và JSON bằng chứng được đính kèm trong report. Khi lỗi, Playwright giữ thêm trace, screenshot và video. Các artifact có thể chứa thông tin tài khoản/dữ liệu demo, vì vậy không commit hoặc chia sẻ công khai.

Lượt mới nhất **09/11/2026** trên database sạch đạt **9/9 PASS, 0 FAIL, 0 SKIP**, trong **102,608 giây**; Browser E2E gate PASS, runner mã 0. FLOW đặt lịch/cọc trên trình duyệt chạy trọn đến khám, hóa đơn, cấp thuốc và review. BILL dùng fixture của Patient 2. Artifact: `e2e-artifacts/dermai-e2e-20261109-final/`; xem [báo cáo](../../docs/e2e-test-evidence-20261109.md).

Lượt lịch sử **08/11/2026** đạt 8 PASS, 0 FAIL, 1 SKIP trong 83,673 giây vì hết slot trong ngày; artifact giữ nguyên tại `e2e-artifacts/dermai-e2e-20261108-final/`.

Lượt lịch sử 06/09/2026 đạt 6/6 PASS trên bộ test cũ trong 55,775 giây; artifact tại `e2e-artifacts/final-2026-09-06/`.
