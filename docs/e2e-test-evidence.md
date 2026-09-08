# Bằng chứng kiểm thử End-to-End DermAI Clinic

## Kết luận

Lượt chạy xác nhận ngày 06/09/2026 trên Chromium đạt **6/6 kịch bản PASS, 0 FAIL, 0 FLAKY và 0 SKIP** trong **55,775 giây**. Đây là kiểm thử E2E bằng Playwright qua giao diện và API thật của hệ thống; phần này độc lập với Postman Collection No E2E.

## Môi trường

- Stack Docker Compose cô lập: Frontend '13000', API Gateway '18080', AI Service '18000'.
- PostgreSQL 16 dùng database 'dermai_e2e' và volume riêng, không sử dụng database local chính.
- Dữ liệu kiểm thử gồm hai Patient, một Receptionist và Doctor **Bác sĩ Vương** có lịch làm việc.
- Ảnh AI là fixture synthetic 'frontend/e2e/fixtures/synthetic-eczema-e2e.png', không chứa dữ liệu bệnh nhân.
- Revision được kiểm tra là snapshot working tree dựa trên commit 'd63572d9cce358c90e0d4325d1e2d947230cf0b0'; các chỉnh sửa E2E chưa commit tại thời điểm chạy.

## Phạm vi đã xác nhận

| ID | Luồng nghiệp vụ | Kết quả |
|---|---|---|
| E2E-AI-001 | Upload ảnh, model thật, lưu kết quả, quyền chia sẻ, chuyển sang đặt lịch | PASS |
| E2E-CHAT-001 | Trợ lý handoff, lễ tân nhận và trả lời, Patient nhận realtime không F5 | PASS |
| E2E-BOOK-001 | Patient giữ và xác nhận slot thật | PASS |
| E2E-BOOK-002 | Hai Patient cạnh tranh cùng slot, một HTTP 201 và một HTTP 409 | PASS |
| E2E-PROPOSAL-001 | Lễ tân gửi đề nghị; Patient chấp nhận một và từ chối một | PASS |
| E2E-FLOW-001 | Đặt lịch đến khám, hồ sơ, đơn thuốc, xem kết quả và review | PASS |

## Nguồn đối chiếu

- Kết quả máy đọc: 'frontend/e2e-artifacts/final-2026-09-06/test-results/e2e-junit.xml' và 'e2e-results.json'.
- Báo cáo trực quan: 'frontend/e2e-artifacts/final-2026-09-06/playwright-report/index.html'.
- Mỗi kịch bản có video; screenshot và JSON nghiệp vụ được đính kèm trong báo cáo Playwright.
- Manifest đã duyệt: 'docs/e2e-test-results.json'.

Artifact E2E được giữ cục bộ và không được Git theo dõi vì có thể chứa dữ liệu phiên kiểm thử. Không đưa mật khẩu, token, OTP hoặc dữ liệu bệnh nhân thật vào hồ sơ nộp.
