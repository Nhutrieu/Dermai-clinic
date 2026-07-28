# Kiến trúc phần mềm — DermAI Clinic

## 1. Mục tiêu kiến trúc

DermAI Clinic là hệ thống đặt lịch khám và hỗ trợ chẩn đoán da liễu bằng AI.
Kiến trúc ưu tiên tính đúng đắn của lịch, phân quyền dữ liệu y tế, khả năng tách
AI khỏi nghiệp vụ lâm sàng và khả năng chạy trên máy cá nhân bằng Docker Compose.

Frontend gọi một API Gateway duy nhất. REST phục vụ thao tác cần phản hồi ngay,
WebSocket báo thay đổi realtime, RabbitMQ truyền sự kiện bất đồng bộ và
PostgreSQL là nguồn dữ liệu chuẩn.

## 2. Sơ đồ thành phần

```text
Browser / React
  |-- HTTP + JWT --------------------------------------|
  |-- WebSocket /api/v1/appointments/ws/slots --------|
                                                        v
                                                Spring Cloud Gateway
       |-----------|------------|------------|-----------|----------|
       v           v            v            v           v          v
     Auth       Patient       Doctor     Appointment   Medical   Prescription
                                            |           Record
                                            | RabbitMQ
                                            v
                                      Notification

Gateway ----------------------------------------------------------> AI FastAPI
                         /ai/predict, /ai/chat, /ai/public-chat

Spring services -> PostgreSQL (mỗi service sở hữu một schema logic)
Frontend        -> Nginx
Dev tools       -> MailHog, Adminer
```

## 3. Dịch vụ và quyền sở hữu dữ liệu

| Dịch vụ | Schema/dữ liệu sở hữu | Trách nhiệm |
|---|---|---|
| Gateway | Không lưu nghiệp vụ | Route, xác thực JWT, CORS và security header |
| Auth Service | `auth` | Identity, email, password hash, role, trạng thái, refresh token, OTP |
| Patient Service | `patient` | Hồ sơ Patient, điện thoại chuẩn hóa, liên kết tài khoản hotline |
| Doctor Service | `doctor` | Hồ sơ Doctor, avatar lưu DB, mô tả, lịch làm và nghỉ phép |
| Appointment Service | `appointment` | Lịch, hold/proposal, Scheduling Engine, closures, notification trong web, reminder, support chat, review và outbox |
| Medical Record Service | `medical_record` | Hồ sơ khám đã ký và chẩn đoán cuối |
| Prescription Service | `prescription` | Đơn thuốc và mục thuốc đã ký |
| Notification Service | `notification` | Trạng thái giao email, số lần thử và idempotency theo event ID |
| AI Service | File/checkpoint/index | Inference ảnh, Grad-CAM, RAG trích xuất và Gemini public chat |

Môi trường hiện tại dùng **một PostgreSQL instance và schema-per-service**, không
phải database/user vật lý riêng cho từng service. Service không truy cập
repository của service khác; liên hệ đồng bộ qua REST hoặc bất đồng bộ qua event.

Thư mục `services/clinic-service` nếu xuất hiện trong workspace là mã thử nghiệm
chưa được khai báo trong parent `pom.xml` và `docker-compose.yml`; nó không phải
thành phần runtime chính thức.

## 4. Luồng xác thực

1. Auth Service kiểm tra BCrypt và phát access token 15 phút cùng refresh token
   14 ngày.
2. Refresh token chỉ lưu dạng SHA-256 hash và được rotate mỗi lần sử dụng.
3. Gateway xác minh chữ ký/expiry rồi ghi đè `X-User-Id` và `X-User-Role` trước
   khi chuyển request.
4. Mỗi controller tiếp tục kiểm tra role và quyền sở hữu bản ghi.
5. Service-to-service dùng `X-Service-Token` cho endpoint nội bộ nhạy cảm.

Frontend hiện lưu session trong `sessionStorage`; tự động refresh khi access
token hết hạn là hạng mục cần hoàn thiện. Khi triển khai công khai phải thay JWT
secret, database password và service token mặc định.

## 5. Scheduling Engine

### 5.1. Sinh và lọc slot

- Múi giờ phòng khám: `Asia/Ho_Chi_Minh`.
- Booking window: từ hôm nay đến tối đa 60 ngày.
- Thời lượng yêu cầu: 10–120 phút; giao diện bệnh nhân mặc định 30 phút.
- Slot phải khớp weekday, start/end và `slotMinutes` của ca làm.
- Loại thời gian nghỉ trưa 12:00–13:00, nghỉ phép và ngày phòng khám đóng cửa.
- Loại xung đột ở các trạng thái đang chiếm chỗ.
- Availability trả `AVAILABLE`, `HELD_BY_YOU`, `HELD_BY_OTHER`, `BOOKED` hoặc
  `ON_LEAVE`.

### 5.2. Chấm điểm đề xuất

```text
score = 0.40*specialty
      + 0.25*earliness
      + 0.20*freeCapacity
      + 0.10*continuity
      + 0.05*preference
```

Mỗi thành phần được chặn trong `[0,1]`. Kết quả sắp xếp theo score giảm dần,
sau đó theo thời gian và UUID. API trả `algorithmVersion = weighted-fair-v2`,
timezone và `reasons` như “Đúng chuyên môn”, “Thời gian sớm”, “Cân bằng tải”,
“Bác sĩ từng theo dõi”.

### 5.3. Chống đặt đồng thời

1. Patient tạo `HELD` trong 5 phút hoặc lễ tân tạo `PROPOSED` trong 10 phút.
2. Trước khi ghi, service kiểm tra ca làm và xung đột hiện tại.
3. PostgreSQL exclusion constraint trên doctor/time và patient/time là hàng rào
   cuối cho các trạng thái đang chiếm chỗ.
4. `Idempotency-Key` ngăn tạo đôi khi client retry.
5. Sau commit, WebSocket phát event để client tải lại availability.

## 6. Realtime và thông báo

WebSocket phát các event nhẹ khi slot, lịch, chat và thông báo thay đổi. Nó không
phải nguồn dữ liệu chuẩn; khi nhận event hoặc reconnect, client gọi REST để đọc
trạng thái mới nhất.

Appointment Service lưu thông báo trong web và outbox trong cùng transaction.
Outbox publisher gửi event đến RabbitMQ; Notification Service chống lặp theo
`eventId`, thử gửi email và lưu lỗi. Queue có retry và dead-letter. Binding/routing
key email phải được kiểm thử end-to-end trước production; `published_at` của
outbox không đồng nghĩa email đã được giao.

## 7. AI và ranh giới an toàn

### 7.1. Computer Vision

AI Service tải checkpoint từ `/models/best_model.pth`. Không có file thì health
trả `modelReady=false`; `/predict` trả 503. API kiểm tra MIME, dung lượng tối đa
10 MB và xác minh ảnh bằng Pillow.

Model code hỗ trợ EfficientNet-B0, ResNet50 và ConvNeXt Tiny. Output gồm nhãn
chính, confidence, Top-3, Grad-CAM data URL, model version, `uncertain` và
disclaimer. Kết quả không được ghi tự động vào final diagnosis.

Repository hiện chưa lưu prediction metadata hoặc ảnh bệnh nhân trong object
storage. Nếu bổ sung lưu trữ, phải có consent, quyền truy cập, retention, bỏ
EXIF và không ghi ảnh/PII vào log.

### 7.2. Gemini và RAG

- `/ai/public-chat` gọi Gemini để tư vấn kiến thức chung. Endpoint này không
  phải RAG và hiện không trả citation.
- `/ai/chat` dùng `RagStore` trích xuất đoạn tài liệu từ `vectors.npy` và
  `chunks.json`; nếu thiếu index hoặc không đủ điểm, trả không đủ bằng chứng.
- RAG hiện ở chế độ extractive, chưa phải generator có citation hoàn chỉnh trên
  frontend.
- Cả hai luồng phải từ chối kê đơn/liều thuốc và không nhận PII/ảnh bệnh nhân.

## 8. Triển khai hiện tại

- Docker Compose chạy PostgreSQL, RabbitMQ, Redis, tám Spring service, AI,
  Gateway, Frontend/Nginx, MailHog và Adminer.
- PostgreSQL dùng named volume. RabbitMQ/Redis cần volume riêng nếu dữ liệu hàng
  đợi/cache phải tồn tại qua container recreation.
- Các cổng 5432, 8000, 8080, 8081, 15672 và 8025 chỉ nên mở local; production
  chỉ công khai reverse proxy/TLS.
- Redis hiện có trong hạ tầng nhưng chưa được ứng dụng dùng cho cache/rate limit.
- Healthcheck chứng minh process phản hồi endpoint, không thay thế synthetic
  test cho booking, email và inference model.

## 9. Quyết định công nghệ

- **React + TypeScript + Vite + CSS tự xây dựng:** giao diện bốn vai trò, lazy
  loading và responsive. Dự án không dùng Tailwind CSS.
- **Java 21 + Spring Boot 3:** validation, transaction, JPA và security.
- **PostgreSQL 16:** transaction và exclusion constraint cần cho lịch.
- **RabbitMQ:** truyền event/outbox cho thông báo bất đồng bộ.
- **FastAPI + PyTorch + OpenCV:** inference, Grad-CAM và pipeline AI.
- **Docker Compose:** phù hợp triển khai đồ án trên một máy; không phải hạ tầng
  cloud/HA nếu chưa có orchestration và monitoring tương ứng.

## 10. Hạng mục production còn thiếu

1. Refresh access token tự động và logout gọi endpoint thu hồi refresh token.
2. Rate limit cho login, forgot-password và Gemini public chat.
3. Secret mạnh, TLS, giới hạn CORS/WebSocket origin và security header cho web.
4. Xác minh routing RabbitMQ/email và thêm metric theo dõi dead-letter.
5. Volume/backup, restore drill, metrics, tracing, log tập trung và alert.
6. Browser E2E, accessibility test, load test và kiểm thử AI trên checkpoint thật.
