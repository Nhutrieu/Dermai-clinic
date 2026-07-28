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
| Tuần 14 | Tích hợp upload/predict vào frontend | AI end-to-end cho Patient/Doctor |
| Tuần 15 | Integration, E2E, concurrency, load, security test | Test report và danh sách lỗi đã sửa |
| Tuần 16 | Docker, backup/restore, tài liệu, slide, demo | Release candidate và bộ bàn giao |

## 3. Trạng thái hiện tại của repository

### Đã có

- Microservices Auth, Patient, Doctor, Appointment, Medical Record,
  Prescription, Notification, Gateway và AI.
- RBAC bốn vai trò, hồ sơ, avatar, mô tả bác sĩ, lịch làm và nghỉ phép.
- Booking window 60 ngày, nghỉ trưa, closure, hold 5 phút, proposal 10 phút,
  chống trùng tại database, idempotency và booking concurrency test.
- Realtime slot/chat/notification với reconnect.
- Hotline/đặt hộ, liên kết hồ sơ theo điện thoại, reminder, no-show, tự hủy lịch
  quá ngày, follow-up, review và dashboard frontend.
- Backend AI có upload validation, Top-3 và Grad-CAM; Gemini public chat.
- Docker resource limit, healthcheck, Nginx gzip/cache và frontend lazy loading.

### Chưa hoàn tất hoặc phải xác minh

- Checkpoint AI, dataset trong workspace và metric test độc lập.
- Giao diện tải ảnh/xem kết quả AI và lưu prediction có consent.
- RAG index, citation trên frontend và bộ đánh giá RAG.
- Tự refresh access token sau 15 phút.
- Routing/email RabbitMQ end-to-end, rate limit, production secret/TLS/origin.
- Browser E2E, accessibility audit, load/security test và restore drill.
- Monitoring, tracing, alert và volume bền vững cho RabbitMQ/Redis.

## 4. Chiến lược kiểm thử

| Lớp kiểm thử | Nội dung | Trạng thái |
|---|---|---|
| Unit | Phone normalization, appointment state, scheduling score, auth, AI policy | Có một phần; tiếp tục mở rộng |
| Integration | Flyway, repository, REST giữa service, outbox/RabbitMQ, hotline relink | Có migration/runtime test; cần tự động hóa thêm |
| Concurrency | Hai người giữ/đặt cùng slot, hủy trong lúc đặt | Đã có booking race script; bổ sung hold race |
| Realtime | Reconnect, nhiều tab, slot/chat/notification event | Có Vitest cho reconnect; cần browser test |
| E2E | Đăng ký → đặt → xác nhận → khám → đơn → review | Chưa có Playwright/Cypress |
| AI data | File hỏng, duplicate hash, leakage, class count | Có validator; chưa có dataset report chính thức |
| AI model | Metric, confusion matrix, latency, deterministic inference | Chờ checkpoint/test set |
| RAG | Refusal/no-evidence, retrieval, citation, injection | Có policy unit test; chưa có index/evaluation |
| Security | Authorization matrix, secret scan, upload fuzz, rate limit | Có role check; cần audit tự động |
| Performance | Booking race, availability, dashboard, inference | Booking race có; các phần khác chưa đo |

Không ghi “đã có Testcontainers/OpenAPI contract/k6/OWASP scan” nếu pipeline chưa
thực sự chạy các công cụ đó. Đây là các mục tiêu nên bổ sung, không phải trạng
thái hiện tại.

## 5. Kịch bản demo bắt buộc

1. Patient đăng ký và cập nhật số điện thoại/hồ sơ.
2. Chọn Doctor/ngày/slot, giữ chỗ và xác nhận lịch.
3. Mở tab Patient khác để chứng minh slot biến mất realtime và không đặt trùng.
4. Lễ tân tìm Patient, xem chat, đặt hộ/đề nghị lịch và gửi nhắc.
5. Doctor xem lịch, bắt đầu khám, ghi hồ sơ, ký đơn và yêu cầu tái khám.
6. Patient xem hồ sơ/đơn, đặt tái khám và đánh giá; Admin duyệt review.
7. Upload một ảnh hợp lệ vào AI, hiển thị Top-3/Grad-CAM/disclaimer; thử ảnh lỗi.
8. Chứng minh model thiếu trả 503 và chatbot từ chối kê đơn.

Kịch bản số 7 chỉ đưa vào bảo vệ sau khi có checkpoint và UI thật; không dùng
response giả hoặc metric không tái lập được.

## 6. Checklist trước khi chạy demo

- [ ] `docker compose ps` cho thấy mọi service cần dùng đều healthy.
- [ ] PostgreSQL đã backup và còn đủ dung lượng ổ đĩa.
- [ ] Tài khoản demo cho bốn role đã kiểm tra, không dùng dữ liệu thật.
- [ ] Slot, hold, cancel, realtime, chat và notification trong web hoạt động.
- [ ] Nếu demo AI: `modelReady=true`, model version đúng và ảnh mẫu hợp lệ.
- [ ] Gemini key còn hiệu lực nhưng không xuất hiện trong Git/log/slide.
- [ ] MailHog/email chỉ demo sau khi queue routing đã được xác minh.
- [ ] Có video quay dự phòng và ảnh chụp metric/model card.

## 7. Checklist production

### Bắt buộc

- Thay `JWT_SECRET`, database password, RabbitMQ credential, service token và
  Gemini key; không dùng default trong Compose.
- TLS, reverse proxy, CORS/origin cụ thể; đóng cổng Postgres, AI, Adminer,
  RabbitMQ Management và MailHog khỏi Internet.
- Rate limit login, forgot-password, public chat và upload.
- Access token auto refresh; logout thu hồi refresh token.
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
