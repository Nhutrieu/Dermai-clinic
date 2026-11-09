# Bằng chứng kiểm thử End-to-End DermAI Clinic

Lượt mới nhất **09/11/2026** đạt **9/9 PASS, 0 FAIL, 0 SKIP**, 102,608 giây; đã chạy trọn bài đặt lịch cùng ngày đến khám/hóa đơn/cấp thuốc/review. **Browser E2E gate PASS**, runner mã 0. Xem [báo cáo mới nhất](e2e-test-evidence-20261109.md) và [manifest](e2e-test-results-20261109.json). PayOS giả lập, AI/RAG thật.

Lượt lịch sử **08/11/2026**: **8 PASS, 0 FAIL, 1 SKIP / 9 kịch bản**, đã kiểm tra cọc/hoàn cọc và ca khám fixture qua hóa đơn/cấp thuốc. Gate của lượt đó BLOCKED vì ca đặt lịch cùng ngày hết slot. Xem [báo cáo ngày 08/11](e2e-test-evidence-20261108.md) và [manifest](e2e-test-results-20261108.json). Nội dung bên dưới là bằng chứng lịch sử ngày 06/09.

## Kết luận

Lượt chạy xác nhận ngày 06/09/2026 trên Chromium đạt **6/6 kịch bản PASS, 0 FAIL, 0 FLAKY và 0 SKIP** trong **55,775 giây**. Đây là kiểm thử E2E bằng Playwright qua giao diện và API thật của hệ thống; phần này độc lập với Postman Collection No E2E.

Đây là bằng chứng lịch sử của snapshot nêu bên dưới. Sáu kịch bản chưa bao gồm
đặt cọc PayOS, hoàn cọc, hóa đơn sau khám hoặc cấp thuốc theo lô trong phạm vi
hiện tại; không dùng kết quả này để kết luận các luồng mới đã pass.

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
