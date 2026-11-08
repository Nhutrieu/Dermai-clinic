# Kế hoạch thực hiện, kiểm thử và triển khai

## 1. Nguyên tắc ưu tiên

Đề tài có phạm vi rộng nên thứ tự ưu tiên là:

1. **Đặt lịch đúng và không trùng** — chức năng bắt buộc.
2. **Quy trình khám năm vai trò** — từ đăng ký, đặt cọc đến hóa đơn và cấp thuốc.
3. **Computer Vision hỗ trợ chẩn đoán** — checkpoint, metric và UI hoàn chỉnh.
4. **Bảo mật, test và khả năng trình diễn ổn định**.
5. Gemini/RAG, đối soát tài chính, kho theo lô và giới hạn y tế của AI.

## 2. Kế hoạch chuẩn 16 tuần

Bảng này là kế hoạch tham chiếu của giai đoạn đầu; phạm vi hiện tại đã mở rộng
thêm Payment Service, hóa đơn và Inventory Service. Trạng thái thực tế được ghi
ở mục 3, không suy ra từ mốc tuần trong bảng.

| Thời gian | Công việc | Đầu ra |
|---|---|---|
| Tuần 1–2 | Khảo sát phòng khám, xác định actor/phạm vi, SRS, Use Case | SRS và tiêu chí nghiệm thu |
| Tuần 3 | Thiết kế Microservices, bảo mật, luồng dữ liệu | SAD, architecture/deployment diagram |
| Tuần 4 | ERD, trạng thái lịch, API contract, migration | ERD, sequence, API draft |
| Tuần 5–6 | Auth, Patient, Doctor, RBAC, hồ sơ, lịch làm/nghỉ | Luồng tài khoản và unit test |
| Tuần 7–8 | Hold, booking, conflict constraint, scheduling, realtime | Luồng đặt lịch + booking race test |
| Tuần 9 | Frontend bốn vai trò ban đầu, hotline, chat, thông báo | UI responsive và điều phối lễ tân |
| Tuần 10 | Medical record, prescription, follow-up, review, dashboard | Quy trình khám hoàn chỉnh |
| Tuần 11 | Kiểm tra dữ liệu AI, split và class mapping | Dataset report và validator |
| Tuần 12–13 | Huấn luyện/so sánh model, metric, Grad-CAM | Checkpoint, test metric, model card |
| Tuần 14 | Tích hợp upload/predict vào frontend | AI end-to-end cho Patient |
| Tuần 15 | Integration, E2E, concurrency, load, security test | Test report và danh sách lỗi đã sửa |
| Tuần 16 | Docker, backup/restore, tài liệu, slide, demo | Release candidate và bộ bàn giao |

## 3. Trạng thái hiện tại của repository

### Đã có

- Chín module Spring runtime gồm Gateway, Auth, Patient, Doctor, Appointment,
  Payment, Medical Record, Prescription và Notification; AI và Inventory là hai
  dịch vụ FastAPI.
- RBAC năm vai trò (`PATIENT`, `DOCTOR`, `RECEPTIONIST`, `PHARMACIST`, `ADMIN`),
  hồ sơ, avatar, mô tả bác sĩ, lịch làm và nghỉ phép.
- Booking window 60 ngày, nghỉ trưa, closure, hold 5 phút, proposal 10 phút,
  tối đa ba lịch active/Patient, chống trùng tại database, idempotency và booking
  concurrency test.
- Giá khám theo Doctor và `consultation_fee_snapshot` trên từng lịch; đặt cọc
  qua PayOS, trạng thái chờ thanh toán/chờ lễ tân xác nhận, yêu cầu hoàn cọc.
- Danh mục dịch vụ, xác nhận dịch vụ đã làm, hóa đơn sau khám, thu tiền mặt hoặc
  PayOS, báo cáo/CSV đối soát và điều chỉnh hóa đơn có lý do.
- Quầy dược, nhập/xuất lô thuốc theo FEFO, nhật ký biến động và cảnh báo tồn.
- Realtime slot/chat/notification với reconnect.
- Hotline/đặt hộ, liên kết hồ sơ theo điện thoại, reminder, check-in, no-show,
  follow-up, review, audit thao tác nhân sự và dashboard frontend.
- Chat hỗ trợ có cơ chế lễ tân nhận/trả cuộc trò chuyện nguyên tử; Admin chỉ
  giám sát, không trực tiếp trả lời.
- Backend AI có upload validation, Top-3 và Grad-CAM; giao diện Patient có lịch
  sử metadata và ảnh gốc, chia sẻ có lựa chọn với Doctor phụ trách, xóa lịch sử
  và chuyển kết quả sang đặt lịch; Gemini public chat.
- Docker resource limit, healthcheck, Nginx gzip/cache và frontend lazy loading.
- Frontend tự refresh access token một lần khi gặp 401 và logout thu hồi refresh
  token.
- Ảnh AI được mã hóa khi lưu, ghi consent/audit và có tác vụ dọn ảnh theo thời
  hạn cấu hình; cần xác minh tác vụ trên môi trường triển khai.

### Chưa hoàn tất hoặc phải xác minh

- Đã có checkpoint EfficientNet-B0 cục bộ, dataset report, metric trên test cố định cũ
  (chưa độc lập theo người; xem [audit ảnh cùng cảnh](47-audit-anh-trung-gan-test-cu.md)),
  calibration, phân tích lỗi, OOD sanity check và latency CPU/GPU. OOD sanity
  check hiện thất bại 0/6 ảnh bị từ chối; còn thiếu đánh giá chuyên môn, tập OOD
  lâm sàng có nhãn và nhiều seed. Browser E2E ngày 06/09/2026 đã chạy trên runtime
  thật với kết quả 6/6 Pass, 0 Fail, 0 Skip trong 55,775 giây. Lượt chạy dùng stack
  PostgreSQL E2E cô lập; stack và volume đã được tự động xóa sau khi hoàn tất.
- RAG đã có index và citation trên frontend; còn thiếu bộ đánh giá retrieval bởi
  chuyên gia, citation validator và kiểm thử prompt injection mở rộng.
- Routing/email RabbitMQ end-to-end, mở rộng rate limit Gateway, production
  secret/TLS/origin và kiểm tra webhook PayOS trên môi trường thực.
- Browser E2E ở revision cũ đã xanh; vẫn cần chạy lại cho thanh toán, hóa đơn,
  kho, hotline, WebSocket reconnect,
  các nhánh âm, accessibility audit, load/security test và restore drill.
- Monitoring, tracing, alert và volume bền vững cho RabbitMQ/Redis.
- Kiểm chứng retention ảnh AI và quota dung lượng PostgreSQL khi vận hành dài hạn.
- Luồng thanh toán/hoàn cọc, hóa đơn và kho đã có mã và test liên quan nhưng
  chưa có bằng chứng chạy lại toàn bộ release suite sau các thay đổi này.

## 4. Chiến lược kiểm thử

Repository có Vitest, JUnit, Pytest và Playwright. Số file không phải số test
case đã pass; kết quả phải lấy từ artifact của từng lần chạy. Bằng chứng 6/6 E2E
thuộc lượt chạy trước các luồng thanh toán/kho hiện tại, nên không coi là kết quả
nghiệm thu các luồng mới.

| Lớp kiểm thử | Nội dung | Trạng thái |
|---|---|---|
| Unit | Phone normalization, appointment state, scheduling score, auth, AI policy | Có một phần; tiếp tục mở rộng |
| Integration | Flyway, repository, REST giữa service, outbox/RabbitMQ, hotline relink | Có migration/runtime test; cần tự động hóa thêm |
| Concurrency | Hai người giữ/đặt cùng slot, hủy trong lúc đặt | Playwright hold race live đã PASS: đúng một người thắng, người còn lại nhận 409 và UI cập nhật; nhánh hủy trong lúc đặt vẫn cần test riêng |
| Realtime | Reconnect, nhiều tab, slot/chat/notification event | Có Vitest reconnect và một phần browser state update; reconnect browser thật vẫn còn thiếu |
| E2E | Giữ slot/đặt, cạnh tranh, lifecycle, AI share, chat handoff và thanh toán | Có bằng chứng 6/6 Pass ngày 06/09/2026; các spec thanh toán/hóa đơn/kho cần chạy và ghi kết quả mới |
| AI data | File hỏng, duplicate hash, leakage, class count | Đã có validator/report; còn thiếu nguồn, giấy phép và near-duplicate |
| AI model | Metric, confusion matrix, latency, deterministic inference | Đã có checkpoint/metric/confusion matrix/calibration/error analysis/latency; còn thiếu nhiều seed, OOD lâm sàng và duyệt chuyên môn |
| RAG | Refusal/no-evidence, retrieval, citation, injection | Đã có index PDF, citation UI và policy test; chưa có expert evaluation |
| Security | Authorization matrix, stored XSS, secret scan, upload fuzz, rate limit | Đã có targeted test cho ownership/quan hệ điều trị, service token và Admin XSS; còn thiếu full matrix, scan/fuzz và rate limit |
| Performance | Booking race, availability, dashboard, inference | Race E2E đã PASS và đã đo latency model CPU/CUDA; API booking/dashboard chưa benchmark |

Không ghi “đã có Testcontainers/OpenAPI contract/k6/OWASP scan” nếu pipeline chưa
thực sự chạy các công cụ đó. Đây là các mục tiêu nên bổ sung, không phải trạng
thái hiện tại.

## 5. Kịch bản demo bắt buộc

1. Patient đăng ký và cập nhật số điện thoại/hồ sơ.
2. Chọn Doctor/ngày/slot, giữ chỗ, xác nhận yêu cầu và thanh toán cọc bằng PayOS
   fake mode trong demo; kiểm tra lịch sang `PENDING_CONFIRMATION`.
3. Mở tab Patient khác để chứng minh slot biến mất realtime và không đặt trùng.
4. Lễ tân xác nhận lịch đã cọc, tìm Patient, xem chat, đặt hộ/đề nghị lịch và gửi nhắc.
5. Patient hỏi trợ lý về giá, sau đó yêu cầu đổi lịch; chuyển yêu cầu sang lễ tân
   và chứng minh hộp thư cập nhật realtime.
6. Doctor xem lịch, bắt đầu khám, lập hồ sơ/đơn khi cần, xác nhận dịch vụ đã làm
   rồi hoàn tất lượt khám.
7. Lễ tân lập hóa đơn khấu trừ cọc và thu phần còn lại; dược sĩ xuất thuốc từ
   đơn đã thanh toán theo FEFO và kiểm tra nhật ký kho.
8. Patient xem lịch sử, đặt tái khám và đánh giá; Admin duyệt review, đối soát hóa đơn.
9. Patient upload một ảnh hợp lệ vào AI, xem Top-3/Grad-CAM/disclaimer, chọn chia
   sẻ rồi chuyển sang đặt lịch; thử ảnh lỗi và xóa một mục lịch sử.
10. Chứng minh model thiếu trả 503 và chatbot từ chối kê đơn.

Kịch bản số 9 dùng checkpoint và UI thật; không dùng response giả hoặc metric
không tái lập được.

## 6. Checklist trước khi chạy demo

- [ ] `docker compose ps` cho thấy mọi service cần dùng đều healthy.
- [ ] PostgreSQL đã backup và còn đủ dung lượng ổ đĩa.
- [ ] Tài khoản demo cho năm role đã kiểm tra, không dùng dữ liệu thật.
- [ ] PayOS fake mode chỉ bật trong stack demo; cọc, hoàn cọc, hóa đơn và xuất
      kho đã được chạy thử với dữ liệu mô phỏng.
- [ ] Slot, hold, cancel, realtime, chat và notification trong web hoạt động.
- [ ] Nếu demo AI: `modelReady=true`, model version đúng và ảnh mẫu hợp lệ.
- [ ] Gemini key còn hiệu lực nhưng không xuất hiện trong Git/log/slide.
- [ ] Gmail SMTP đã gửi thử OTP và email trạng thái lịch khám thành công.
- [ ] Có video quay dự phòng và ảnh chụp metric/model card.

## 7. Checklist production

### Bắt buộc

- Thay `JWT_SECRET`, database password, RabbitMQ credential, service token,
  `DATA_ENCRYPTION_KEY`, PayOS key và Gemini key; không dùng default trong Compose.
- TLS, reverse proxy, CORS/origin cụ thể; đóng cổng Postgres, AI, Inventory, Adminer,
  RabbitMQ Management khỏi Internet; chỉ cho phép kết nối SMTP đi ra qua TLS.
- Rate limit login, forgot-password, public chat và upload.
- Backup tự động, restore drill, retention và consent ảnh.
- RabbitMQ persistent volume, publisher confirm/return hoặc cơ chế xác minh giao
  event; theo dõi dead-letter.
- Structured log có request ID, metrics, alert 5xx/latency/DB/queue/disk.

### Riêng cho AI

- Dataset/version/checksum, checkpoint checksum, model card và approval.
- Test metric, subgroup/error analysis và latency trên phần cứng triển khai.
- Ngưỡng uncertain, rollback model và giám sát drift/phản hồi sai.
- Ảnh private, bỏ EXIF, access control và quy tắc xóa dữ liệu.

## 8. Sản phẩm bàn giao

- Source frontend, Spring services, AI, migration và test/script.
- Docker Compose, `.env.example`, hướng dẫn cài đặt và backup/restore.
- SRS, SAD, API, AI/RAG guide, model card, [DBML ERD](../database/dermai_erd.dbml)
  và hướng dẫn triển khai production.
- Dataset report, checkpoint, metric/confusion matrix và Grad-CAM mẫu khi hoàn tất.
- Test report, hướng dẫn năm vai trò, slide và kịch bản demo.
