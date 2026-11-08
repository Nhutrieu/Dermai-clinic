# Bằng chứng kiểm thử DermAI Clinic

Chỉ ghi `PASS` cho kết quả đã được chạy và đối chiếu với một revision xác định.
Revision phải gồm commit và cờ `workingTreeDirty`; nếu working tree đang dirty,
báo cáo phải ghi rõ đây là snapshot chưa commit, không được gắn kết quả cho riêng
commit cha. Không suy ra `PASS` từ việc chức năng xuất hiện trên giao diện và
không chép dữ liệu bệnh nhân thật, mật khẩu, OTP hoặc API key vào báo cáo.

## Nguồn bằng chứng

- `tests/run-release-tests.ps1` chạy build frontend, Vitest, Maven, Pytest và xác
  minh SHA-256 checkpoint. Khi không truyền `-IncludeE2E`, Browser E2E được ghi
  `NOT_RUN`; khi có truyền, thiếu/stale/không hợp lệ JUnit không thể trở thành
  `PASS`. Script chỉ trả mã thoát `0` khi toàn bộ release gate là `PASS`; trạng
  thái `FAIL`, `BLOCKED` hoặc `NOT_RUN` đều trả mã khác `0`. Log máy được tạo tại
  `test-results/release/` và không commit.
- Playwright tạo JUnit/JSON, HTML report, trace, ảnh và video tại
  `frontend/test-results/` và `frontend/playwright-report/`. Các artifact này giữ
  cục bộ vì có thể chứa dữ liệu phiên kiểm thử.
- `docs/test-results.json` là manifest đã duyệt để sinh Actual Result/Pass/Fail
  trong `DermAI_Clinic_Test_Cases.docx`. Test case không có trong manifest luôn
  giữ trạng thái `NOT_RUN`.
- `ai-service/reports/ai_evidence/` chứa manifest checkpoint, calibration,
  per-image error theo SHA-256, latency, OOD probes và Grad-CAM metadata. Pytest
  PASS chỉ xác minh code đánh giá; metric model phải lấy từ chính các artifact này.

## Bản chụp kết quả đã lưu

- Manifest Playwright ngày **06/09/2026** ghi **6/6 PASS, 0 FAIL, 0 SKIP** trong
  55,775 giây trên stack PostgreSQL E2E cô lập. Xem
  [`e2e-test-evidence.md`](e2e-test-evidence.md) và
  [`e2e-test-results.json`](e2e-test-results.json) để biết revision và sáu scenario.
  Lượt này chưa kiểm chứng các luồng thanh toán, hóa đơn và kho hiện tại.
- Manifest 81 test case ánh xạ bảo thủ **13 PASS, 1 FAIL, 67 NOT_RUN**. Năm
  scenario Playwright thuộc snapshot ngày 14/08/2026 (`docs/test-results.json`),
  không phải kết quả của lượt 6/6 ngày 06/09. Chỉ case có đủ assertion cho toàn
  bộ kết quả mong đợi mới được ghi PASS.
- Test case mở rộng cho đặt cọc, hóa đơn và kho trong
  [`07-test-cases-extended.md`](07-test-cases-extended.md) vẫn `NOT_RUN` cho đến
  khi có kết quả và artifact theo revision mới.
- Checkpoint promoted có SHA-256
  `914f83a85c4dbff06424e0a48f1121950f10e3c0ce8d5a9f68369b38106cc3df`,
  khớp file model, evaluation manifest và model comparison report.
- OOD sanity: **FAIL/known limitation** — 0/6 probe phi lâm sàng bị từ chối ở
  ngưỡng 0,55. Đây không phải benchmark OOD lâm sàng.
- Test case mới dành riêng cho ownership hồ sơ y tế, Admin stored XSS, service
  token và model evidence là `SEC-001..005` và `AI-008..011`.

## Quy ước

- `PASS`: toàn bộ bước và kết quả mong đợi đã được quan sát hoặc được test tự
  động tương đương kiểm chứng.
- `FAIL`: có ít nhất một sai khác; phải kèm mã defect và bằng chứng.
- `BLOCKED`: không thể chạy do thiếu runtime, tài khoản/dữ liệu test hoặc phụ
  thuộc bên ngoài.
- `NOT_RUN`: chưa thực thi; không tính vào số Pass.

Generator từ chối test case ID không tồn tại, kết quả đã chạy thiếu Actual Result
hoặc Evidence, và mọi `FAIL` không có Defect ID. Điều này ngăn bảng Word vô tình
hiển thị một kết quả không có nguồn đối chiếu.

Chỉ đưa ảnh/video cần thiết vào hồ sơ nộp riêng sau khi đã kiểm tra không chứa
thông tin nhạy cảm. Không đưa trace đăng nhập hoặc storage state lên Git.
