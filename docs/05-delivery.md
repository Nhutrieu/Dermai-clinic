# Kế hoạch thực hiện, kiểm thử và triển khai

## 1. Nguyên tắc ưu tiên

Đề tài có phạm vi rộng nên thứ tự ưu tiên là:

1. **Đặt lịch đúng và không trùng** — chức năng bắt buộc.
2. **Quy trình khám bốn vai trò** — từ đăng ký đến hồ sơ/đơn/tái khám.
3. **Computer Vision hỗ trợ chẩn đoán** — checkpoint, metric và UI hoàn chỉnh.
4. **Bảo mật, test và khả năng trình diễn ổn định**.
5. Gemini/RAG, analytics nâng cao, SMS và cloud là phần mở rộng.

## 2. Kế hoạch chuẩn 16 tuần

| Thời gian | Công việc | Đầu ra |
|---|---|---|
| Tuần 1–2 | Khảo sát phòng khám, xác định actor/phạm vi, SRS, Use Case | SRS và tiêu chí nghiệm thu |
| Tuần 3 | Thiết kế Microservices, bảo mật, luồng dữ liệu | SAD, architecture/deployment diagram |
| Tuần 4 | ERD, trạng thái lịch, API contract, migration | ERD, sequence, API draft |
| Tuần 5–6 | Auth, Patient, Doctor, RBAC, hồ sơ, lịch làm/nghỉ | Luồng tài khoản và unit test |
| Tuần 7–8 | Hold, booking, conflict constraint, scheduling, realtime | Luồng đặt lịch + booking race test |
| Tuần 9 | Frontend bốn vai trò, hotline, chat, thông báo | UI responsive và điều phối lễ tân |
| Tuần 10 | Medical record, prescription, follow-up, review, dashboard | Quy trình khám hoàn chỉnh |
| Tuần 11 | Kiểm tra dữ liệu AI, split và class mapping | Dataset report và validator |
| Tuần 12–13 | Huấn luyện/so sánh model, metric, Grad-CAM | Checkpoint, test metric, model card |
| Tuần 14 | Tích hợp upload/predict vào frontend | AI end-to-end cho Patient |
| Tuần 15 | Integration, E2E, concurrency, load, security test | Test report và danh sách lỗi đã sửa |
| Tuần 16 | Docker, backup/restore, tài liệu, slide, demo | Release candidate và bộ bàn giao |

## 3. Trạng thái hiện tại của repository

### Đã có

- Microservices Auth, Patient, Doctor, Appointment, Medical Record,
  Prescription, Notification, Gateway và AI.
- RBAC bốn vai trò, hồ sơ, avatar, mô tả bác sĩ, lịch làm và nghỉ phép.
- Booking window 60 ngày, nghỉ trưa, closure, hold 5 phút, proposal 10 phút,
  tối đa ba lịch active/Patient, chống trùng tại database, idempotency và booking
  concurrency test.
- Giá khám cố định theo Doctor và `consultation_fee_snapshot` trên từng lịch;
  thanh toán trực tiếp tại phòng khám, chưa có hóa đơn/thanh toán online.
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

### Chưa hoàn tất hoặc phải xác minh

- Đã có checkpoint EfficientNet-B0 cục bộ, dataset report, metric test độc lập,
  calibration, phân tích lỗi, OOD sanity check và latency CPU/GPU. OOD sanity
  check hiện thất bại 0/6 ảnh bị từ chối; còn thiếu đánh giá chuyên môn, tập OOD
  lâm sàng có nhãn và nhiều seed. Browser E2E đã chạy trên runtime thật với kết
  quả gần nhất 5/5 Pass, 0 Fail, 0 Skip trong 38,798 giây. Lượt chạy dùng stack
  PostgreSQL E2E cô lập; stack và volume đã được tự động xóa sau khi hoàn tất.
- RAG đã có index và citation trên frontend; còn thiếu bộ đánh giá retrieval bởi
  chuyên gia, citation validator và kiểm thử prompt injection mở rộng.
- Routing/email RabbitMQ end-to-end, rate limit, production secret/TLS/origin.
- Browser E2E release hiện đã xanh; vẫn cần bổ sung hotline, WebSocket reconnect,
  các nhánh âm, accessibility audit, load/security test và restore drill.
- Monitoring, tracing, alert và volume bền vững cho RabbitMQ/Redis.
- Chính sách retention/xóa tự động và quota dung lượng cho ảnh AI lưu trong
  PostgreSQL.

## 4. Chiến lược kiểm thử

Tại thời điểm cập nhật tài liệu, repository có 21 file Vitest frontend, 23 file
JUnit Java, 5 file Pytest và 3 Playwright spec. Đây là số file kiểm thử, không
phải số test case đã pass; kết quả phải lấy từ lần chạy CI/local gần nhất.

| Lớp kiểm thử | Nội dung | Trạng thái |
|---|---|---|
| Unit | Phone normalization, appointment state, scheduling score, auth, AI policy | Có một phần; tiếp tục mở rộng |
| Integration | Flyway, repository, REST giữa service, outbox/RabbitMQ, hotline relink | Có migration/runtime test; cần tự động hóa thêm |
| Concurrency | Hai người giữ/đặt cùng slot, hủy trong lúc đặt | Playwright hold race live đã PASS: đúng một người thắng, người còn lại nhận 409 và UI cập nhật; nhánh hủy trong lúc đặt vẫn cần test riêng |
| Realtime | Reconnect, nhiều tab, slot/chat/notification event | Có Vitest reconnect và một phần browser state update; reconnect browser thật vẫn còn thiếu |
| E2E | Giữ slot/đặt, cạnh tranh, lifecycle, AI share và chat handoff | Lần live gần nhất 5/5 Pass, 0 Fail, 0 Skip; 38,798 giây; 9 PNG và 5 video; chạy trên database cô lập đã được xóa sau test |
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
2. Chọn Doctor/ngày/slot, giữ chỗ và xác nhận lịch.
3. Mở tab Patient khác để chứng minh slot biến mất realtime và không đặt trùng.
4. Lễ tân tìm Patient, xem chat, đặt hộ/đề nghị lịch và gửi nhắc.
5. Patient hỏi trợ lý về giá, sau đó yêu cầu đổi lịch; chuyển yêu cầu sang lễ tân
   và chứng minh hộp thư cập nhật realtime.
6. Doctor xem lịch, bắt đầu và hoàn tất lượt khám; minh họa hồ sơ/đơn thuốc như
   chức năng bổ trợ, không bắt buộc để hoàn tất.
7. Patient xem lịch sử, đặt tái khám và đánh giá; Admin duyệt review.
8. Patient upload một ảnh hợp lệ vào AI, xem Top-3/Grad-CAM/disclaimer, chọn chia
   sẻ rồi chuyển sang đặt lịch; thử ảnh lỗi và xóa một mục lịch sử.
9. Chứng minh model thiếu trả 503 và chatbot từ chối kê đơn.

Kịch bản số 8 dùng checkpoint và UI thật; không dùng response giả hoặc metric
không tái lập được.

## 6. Checklist trước khi chạy demo

- [ ] `docker compose ps` cho thấy mọi service cần dùng đều healthy.
- [ ] PostgreSQL đã backup và còn đủ dung lượng ổ đĩa.
- [ ] Tài khoản demo cho bốn role đã kiểm tra, không dùng dữ liệu thật.
- [ ] Slot, hold, cancel, realtime, chat và notification trong web hoạt động.
- [ ] Nếu demo AI: `modelReady=true`, model version đúng và ảnh mẫu hợp lệ.
- [ ] Gemini key còn hiệu lực nhưng không xuất hiện trong Git/log/slide.
- [ ] Gmail SMTP đã gửi thử OTP và email trạng thái lịch khám thành công.
- [ ] Có video quay dự phòng và ảnh chụp metric/model card.

## 7. Checklist production

### Bắt buộc

- Thay `JWT_SECRET`, database password, RabbitMQ credential, service token và
  Gemini key; không dùng default trong Compose.
- TLS, reverse proxy, CORS/origin cụ thể; đóng cổng Postgres, AI, Adminer,
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
- SRS, SAD, API, AI/RAG guide, model card và sơ đồ trong `docs/diagrams`.
- Dataset report, checkpoint, metric/confusion matrix và Grad-CAM mẫu khi hoàn tất.
- Test report, hướng dẫn bốn vai trò, slide và kịch bản demo.
