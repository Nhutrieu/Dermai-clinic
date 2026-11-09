# E2E DermAI Clinic — 08/11/2026

Lượt xác nhận trên database sạch đạt **8 PASS, 0 FAIL, 0 FLAKY, 1 SKIP / 9 kịch bản**, trong **83,673 giây**. Release gate còn **BLOCKED**, runner trả mã `2` vì vẫn có SKIP; không ghi toàn bộ suite PASS.

## Bản đã kiểm tra

- Commit nền: `be801397561f8cc0a3df9998241bc4fcc3f20177`, **workingTreeDirty=true**. Kết quả thuộc snapshot chưa commit, gồm các thay đổi AI hiện có và các sửa lỗi E2E/frontend trong lượt này.
- Stack `dermai-e2e-20261108-final`, build từ mã hiện tại; PostgreSQL 16/volume mới, tài khoản tổng hợp, Chromium/Playwright, múi giờ `Asia/Ho_Chi_Minh`.
- Web qua Nginx/gateway tại `http://localhost:53000`; 15 container healthy trước khi chạy. Không intercept hoặc mock API nghiệp vụ.
- PayOS dùng **FakePayOSGateway**; không chuyển tiền thật. Kết quả không xác nhận kết nối/webhook hay đối soát PayOS thật. SMTP trỏ loopback.
- AI/RAG nạp thật: `modelMode=research_pipeline`, `modelVersion=dermai-eight-esg-v1-20261108`, `modelReady=true`, `ragReady=true`. Ảnh synthetic có sẵn; đây là kiểm tra chức năng, không phải phép đo độ chính xác model.
- Fixture bác sĩ làm hằng ngày, `CLINIC_WEEKLY_CLOSURE_DAY=NONE` chỉ cho stack test. Ca đã cọc được seed riêng để kiểm tra phần sau đặt lịch khi hết slot cùng ngày.

## Kết quả

| ID | Phạm vi | Kết quả |
|---|---|---|
| E2E-AI-001 | Upload, model thật, Top-3/mức đồng thuận, Grad-CAM, lưu/chia sẻ, mở đặt lịch có ngữ cảnh AI | PASS |
| E2E-CHAT-001 | Trợ lý handoff, lễ tân nhận/trả lời, bệnh nhân nhận realtime | PASS |
| E2E-BOOK-001 | Chọn slot, giữ chỗ, thanh toán cọc giả lập, trở về đúng màn hình và trạng thái | PASS |
| E2E-BOOK-002 | Hai bệnh nhân tranh slot: một HTTP 201, một HTTP 409, một lịch thắng | PASS |
| E2E-PAY-001 | Hủy thanh toán, lịch bị hủy và slot được trả lại | PASS |
| E2E-PAY-002 | Cọc thành công, hủy lịch, yêu cầu hoàn, lễ tân hoàn tiền mặt | PASS |
| E2E-PROPOSAL-001 | Bệnh nhân chấp nhận một đề nghị và từ chối đề nghị khác | PASS |
| E2E-FLOW-001 | Một chuỗi từ đặt lịch cùng ngày đến khám/hóa đơn/cấp thuốc/review | **SKIP** |
| E2E-BILL-001 | Từ ca đã cọc chuẩn bị sẵn: xác nhận/check-in, khám/kê đơn/dịch vụ, hóa đơn, thu tiền, xuất thuốc, xem kết quả/review | PASS |

`E2E-FLOW-001` không có slot tương lai đủ 30 phút trong ngày tại thời điểm chạy khoảng 23:40. Giữ nguyên SKIP và lý do trong JSON/JUnit. Kết quả BILL không thay thế bằng chứng đặt lịch cùng ngày của FLOW; cần chạy lại FLOW vào thời điểm còn slot để đóng gate.

## Bằng chứng hóa đơn và kho

- Phí khám 150.000đ + dịch vụ 150.000đ + thuốc 70.000đ = **370.000đ**.
- Cọc **100.000đ**, còn thu **270.000đ**. API từ chối thu thiếu; nhận 320.000đ và trả lại đúng 50.000đ.
- Hóa đơn chưa trả không xuất hiện trong hàng đợi Dược.
- Sau cấp 2 đơn vị thuốc, tồn từ **100 → 98**, hóa đơn đồng bộ `DISPENSED`.
- Gửi lại cùng yêu cầu cấp thuốc nhận **HTTP 409**; tồn vẫn 98.
- Bệnh nhân xem được kết quả/đơn thuốc và gửi review thành công.

## Sửa trong lượt chạy

- Sửa mất điều hướng sau khi quay về thanh toán: chỉ xóa `derm-home-intent` sau React commit, tránh initializer bị chạy lại khi lazy route suspend.
- Bổ sung nhãn tiếng Việt cho lịch chờ cọc/hết hạn cọc.
- Cập nhật test AI theo mức đồng thuận mới; ràng buộc assertion đặt lịch vào đúng dòng lịch và selector thu tiền theo accessible name hiện tại.
- Thêm stack/fixture/runner E2E cô lập, kiểm tra số tiền, tiền thối, giảm tồn kho và chặn xuất lặp.

Build frontend trong Docker và TypeScript E2E đạt; **97/97 Vitest** đạt. Lượt đầu 8 kịch bản có 1 FAIL và 1 SKIP; các lượt điều tra được giữ riêng, không ghi đè. Báo cáo này dùng đúng lượt database sạch cuối cùng sau sửa.

## Đối chiếu và chạy lại

- [Manifest đã đối chiếu](e2e-test-results-20261108.json).
- Artifact cục bộ: `frontend/e2e-artifacts/dermai-e2e-20261108-final/` gồm `revision.json`, `source-hashes.json`, `test-results/e2e-junit.xml`, `test-results/e2e-results.json`, `playwright-report/index.html`, ảnh/video và log.
- JSON nghiệp vụ được đính kèm inline trong Playwright JSON/report. Manifest lưu hash SHA-256 của JUnit và JSON.
- Runner đã dọn stack/volume riêng và file secret; không thay đổi database local chính. Artifact giữ cục bộ, không commit trace/video/token.

```powershell
powershell -ExecutionPolicy Bypass -File tests/run-isolated-e2e.ps1
```

Xem [hướng dẫn E2E](../frontend/e2e/README.md). PayOS thật, hóa đơn online sau khám, tải đồng thời nhiều người dùng và khôi phục backup chưa được nghiệm thu bởi lượt này.
