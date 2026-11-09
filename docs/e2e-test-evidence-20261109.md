# E2E DermAI Clinic — 09/11/2026

Lượt chạy trên database sạch đạt **9/9 PASS, 0 FAIL, 0 SKIP, 0 FLAKY**, trong **102,608 giây**. Runner trả mã **0**; gate **Browser E2E PASS**. Bài `E2E-FLOW-001` bị bỏ qua ngày 08/11 đã chạy trọn vẹn trong lượt này.

## Snapshot và môi trường

- Commit nền `be801397561f8cc0a3df9998241bc4fcc3f20177`, **workingTreeDirty=true**. Kết quả thuộc snapshot chưa commit; `revision.json` ghi các file thay đổi. Đối chiếu **510 file code, 0 sai khác hash** sau khi chạy.
- Stack `dermai-e2e-20261109-final`, build mã hiện tại; PostgreSQL 16 và volume mới, tài khoản tổng hợp. Cả 15 container healthy trước khi chạy Chromium/Playwright, múi giờ `Asia/Ho_Chi_Minh`.
- Web/Nginx/gateway tại `http://localhost:53000`; không intercept API nghiệp vụ. AI/RAG nạp thật: `dermai-eight-esg-v1-20261108`, `modelMode=research_pipeline`, `modelReady=true`, `ragReady=true`.
- PayOS dùng `FakePayOSGateway`, không chuyển tiền thật; SMTP trỏ loopback. Bác sĩ fixture làm hằng ngày, `CLINIC_WEEKLY_CLOSURE_DAY=NONE` chỉ trong stack test.

## Kết quả

| ID | Phạm vi xác nhận | Kết quả |
|---|---|---|
| E2E-AI-001 | Upload, model thật, Top-3/mức đồng thuận, Grad-CAM, lưu/chia sẻ, mở đặt lịch có ngữ cảnh AI | PASS |
| E2E-CHAT-001 | Trợ lý handoff, lễ tân nhận/trả lời, bệnh nhân nhận realtime | PASS |
| E2E-BOOK-001 | Giữ slot, cọc giả lập, trở về đúng màn hình lịch và trạng thái đã cọc | PASS |
| E2E-BOOK-002 | Hai bệnh nhân tranh slot: một HTTP 201, một HTTP 409, chỉ một lịch thắng | PASS |
| E2E-PAY-001 | Hủy thanh toán, hủy lịch và trả slot | PASS |
| E2E-PAY-002 | Cọc, hủy lịch, yêu cầu hoàn và lễ tân hoàn tiền mặt | PASS |
| E2E-PROPOSAL-001 | Chấp nhận một đề nghị lịch và từ chối đề nghị khác | PASS |
| E2E-FLOW-001 | Đặt lịch/cọc trên trình duyệt → xác nhận/check-in → khám/kê đơn/dịch vụ → hóa đơn/thu tiền → cấp thuốc → xem kết quả/review | PASS |
| E2E-BILL-001 | Ca đã cọc chuẩn bị sẵn qua xác nhận/check-in, khám, hóa đơn, cấp thuốc và review | PASS |

FLOW dùng **Patient 1**, bắt đầu bằng đặt lịch và cọc trên trình duyệt, không dùng ca khám seed. BILL dùng ca đã cọc của **Patient 2**. Tách bệnh nhân giúp fixture BILL không chặn FLOW bởi quy tắc cùng bác sĩ/cùng ngày. Đây là thay đổi dữ liệu/test; không nới quy tắc nghiệp vụ của ứng dụng.

## Bằng chứng tiền và kho

Cả hai ca có hóa đơn **370.000đ**: khám 150.000đ, dịch vụ 150.000đ và thuốc 70.000đ. Cọc được trừ đúng **100.000đ**, còn thu **270.000đ**. Thu thiếu bị từ chối HTTP 409; nhận 320.000đ và thối đúng 50.000đ.

- FLOW: tồn **100 → 98**, lịch `COMPLETED`, hóa đơn `DISPENSED`, review thành công.
- BILL: tồn **98 → 96**, lịch `COMPLETED`, hóa đơn `DISPENSED`, review thành công.
- Hóa đơn chưa trả không vào hàng đợi Dược. Gửi lặp yêu cầu xuất thuốc nhận **HTTP 409**, không giảm tồn lần nữa.

## Nguồn đối chiếu và chạy lại

[Manifest](e2e-test-results-20261109.json) đã đối chiếu JUnit và Playwright JSON, lưu SHA-256 của cả hai cùng bằng chứng hai ca khám. Artifact cục bộ tại `frontend/e2e-artifacts/dermai-e2e-20261109-final/`: revision, source hashes, JUnit/JSON, report HTML, ảnh/video và log. JSON nghiệp vụ đính kèm inline trong report. Không ghi đè artifact hoặc kết quả lịch sử ngày 08/11.

```powershell
powershell -ExecutionPolicy Bypass -File tests/run-isolated-e2e.ps1
```

Runner đã dọn container, network, volume và file secret của riêng stack test; database local chính không bị sửa. Xem [hướng dẫn E2E](../frontend/e2e/README.md).

Kết quả này xác nhận chín kịch bản Browser E2E trên snapshot nêu trên. Chưa xác nhận PayOS/webhook thật, hóa đơn online sau khám, tải nhiều người dùng hay toàn bộ release suite. Kiểm tra AI là kiểm tra chức năng, không phải phép đo độ chính xác lâm sàng.
