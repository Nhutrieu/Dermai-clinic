# DermAI Clinic

**Hệ thống đặt lịch và hỗ trợ chẩn đoán y tế bằng AI cho phòng khám da liễu.**

DermAI Clinic kết hợp quy trình đặt lịch khám an toàn, điều phối lễ tân theo thời
gian thực và mô hình Computer Vision hỗ trợ bệnh nhân tham khảo ảnh da trước khi
đến khám.

> AI chỉ phân tích đặc điểm hình ảnh trong tám nhóm dữ liệu của đồ án. Kết quả
> không thay thế việc thăm khám, chẩn đoán hoặc kê đơn của bác sĩ.

## Chức năng chính

### Bệnh nhân

- Đăng ký bằng email OTP, đăng nhập mật khẩu hoặc Google OAuth; access token
  được tự refresh bằng refresh token xoay vòng.
- Xem hồ sơ, mô tả, chuyên môn, kinh nghiệm, lịch trống và giá khám của bác sĩ.
- Chọn bác sĩ, ngày, khung giờ, nhập lý do và xác nhận đặt lịch.
- Xem lịch sắp tới/lịch sử và nhận thông báo. Trợ lý hỗ trợ tự động trả lời thủ
  tục đơn giản; yêu cầu cần thao tác được chuyển sang lễ tân realtime.
- Phân tích ảnh da bằng AI, xem Top-3, confidence, Grad-CAM và hướng dẫn RAG.
- Lưu lịch sử assessment/ảnh, chủ động chia sẻ riêng cho bác sĩ phụ trách, xóa
  kết quả của mình và đánh giá sau buổi khám.

### Lễ tân

- Nhận yêu cầu đặt lịch online theo thời gian thực.
- Xác nhận, đề nghị lịch khác, đổi hoặc hủy lịch theo yêu cầu bệnh nhân.
- Tra cứu bệnh nhân và đặt lịch qua hotline; số điện thoại là bắt buộc.
- Gửi nhắc lịch, check-in, điều phối hàng đợi và ghi nhận no-show.
- Nhận phụ trách cuộc trò chuyện để tránh nhiều lễ tân trả lời cùng lúc.
- Nhận yêu cầu đã được trợ lý phân loại kèm nội dung gốc của bệnh nhân.

### Bác sĩ

- Quản lý hồ sơ nghề nghiệp, ảnh đại diện, mô tả và lịch làm việc hằng tuần.
- Khai báo nghỉ phép, độ dài slot và theo dõi lịch được phân công.
- Xem lý do khám và kết quả AI mà bệnh nhân cho phép chia sẻ.
- Bắt đầu/hoàn tất lượt khám; hồ sơ y khoa, đơn thuốc và tái khám là tùy chọn.

### Quản trị viên

- Quản lý bệnh nhân, bác sĩ và tài khoản nhân sự.
- Cấu hình giá khám từng bác sĩ và ngày phòng khám đóng cửa.
- Kiểm duyệt đánh giá, xem audit và giám sát hộp thư hỗ trợ.
- Theo dõi dashboard vận hành và sửa trạng thái ca khám bị quên cập nhật.

## An toàn đặt lịch

- Chỉ cho đặt lịch trong 60 ngày tiếp theo.
- Slot được giữ tạm thời 5 phút; nhấn lại để nhả hoặc tự giải phóng khi hết hạn.
- Mỗi bệnh nhân có tối đa ba lịch sắp tới đang hoạt động.
- Không đặt hai bác sĩ trùng giờ hoặc cùng một bác sĩ hai lần trong cùng ngày.
- `Idempotency-Key`, khóa giao dịch và PostgreSQL exclusion constraint ngăn hai
  người xác nhận cùng một slot.
- Giá được lưu tại thời điểm đặt bằng `consultation_fee_snapshot`.
- Bệnh nhân chỉ tự đổi/hủy khi lịch chưa được xác nhận và còn trong 30 phút đầu;
  sau đó phải liên hệ lễ tân.
- Slot, yêu cầu đặt lịch, thông báo, avatar và chat được đồng bộ bằng WebSocket.

## AI Computer Vision

Mô hình hiện tại sử dụng **EfficientNet-B0** pretrained ImageNet, fine-tune cho
tám nhóm: Acne, Candidiasis, Eczema, Lupus, Psoriasis, SkinCancer, Tinea và
Warts. `SkinCancer` là nhãn nhóm nguy cơ trong dataset, không phải kết luận mô
bệnh học.

| Tập đánh giá | Số ảnh | Accuracy | Macro F1 | Top-3 Accuracy |
|---|---:|---:|---:|---:|
| Test độc lập | 564 | 78,90% | 78,31% | 93,62% |
| External test | 240 | 67,92% | 41,57% | 92,92% |

External test có phân bố lớp không cân bằng và không có mẫu `SkinCancer`; kết
quả giảm cho thấy domain shift vẫn là giới hạn quan trọng. Xem đầy đủ metric,
confusion matrix và giới hạn sử dụng trong [Model Card hiện tại](docs/model-card-scin-v1.md).

RAG truy xuất nội dung từ tài liệu da liễu để giải thích kiến thức liên quan.
Chatbot không kê đơn và không tạo phác đồ điều trị cá nhân.

Trợ lý hỗ trợ trong khu vực Patient là tầng đầu của một luồng hội thoại thống
nhất. AI hướng dẫn quy trình đặt/đổi/hủy lịch, tìm bác sĩ, giá, giờ làm, cách dùng
và cách đọc kết quả AI; câu hỏi da liễu chung chỉ được trả lời khi RAG local có
nguồn phù hợp. Yêu cầu thao tác lịch, tài khoản, khiếu nại, câu hỏi cá nhân hoặc
nội dung AI không hiểu được tự động chuyển sang lễ tân; Patient không phải mở
một chat mới hay kể lại từ đầu. Gemini chỉ được phép biên tập câu mẫu từ tên nhóm
yêu cầu và không nhận nội dung gốc của bệnh nhân. Appointment Service lưu toàn bộ
transcript `PATIENT / AI / SYSTEM`, intent, điểm khớp quy tắc định tuyến, số lần
thất bại và bản tóm
tắt bàn giao. Lễ tân nhận realtime, xem toàn bộ ngữ cảnh rồi claim conversation
trước khi trả lời trong chính cuộc trò chuyện đó. Khi xử lý xong, lễ tân chọn
`Hoàn tất hỗ trợ`; lịch sử vẫn được giữ nhưng yêu cầu tiếp theo quay lại tầng AI.

Patient Service lưu metadata và ảnh gốc của assessment trong PostgreSQL để
Patient xem lại hoặc chia sẻ; Grad-CAM không được lưu. Doctor chỉ đọc ảnh khi
Patient chia sẻ với đúng lịch mà Doctor phụ trách. Ảnh dùng
`Cache-Control: no-store` và bị xóa khi Patient xóa assessment.

## Kiến trúc hệ thống

```text
Browser
  └─ React + TypeScript + Vite + Nginx
       └─ Spring Cloud Gateway — JWT / RBAC / routing
            ├─ Auth Service
            ├─ Patient Service
            ├─ Doctor Service
            ├─ Appointment Service — booking engine / WebSocket
            ├─ Medical Record Service
            ├─ Prescription Service
            ├─ Notification Service — RabbitMQ / Gmail SMTP
            └─ FastAPI AI Service — EfficientNet-B0 / Grad-CAM / RAG

PostgreSQL 16 · Redis 7 · RabbitMQ 3.13 · Docker Compose
```

| Thành phần | Công nghệ / trách nhiệm |
|---|---|
| Frontend | React, TypeScript, Vite, CSS Design System và Nginx |
| Gateway | Spring Cloud Gateway, JWT, RBAC và định tuyến API |
| Backend | Java 21, Spring Boot 3.4, Spring Data JPA và Flyway |
| Dữ liệu | PostgreSQL 16 với 7 schema và 24 bảng nghiệp vụ |
| Realtime | WebSocket; dữ liệu được tải lại từ nguồn thật sau sự kiện |
| Messaging | RabbitMQ và outbox event cho thông báo bất đồng bộ |
| AI | FastAPI, PyTorch, EfficientNet-B0, Grad-CAM, TF-IDF RAG và Gemini public chat |
| Hạ tầng | Docker Compose, healthcheck và giới hạn RAM từng container |

## Chạy bằng Docker

### Yêu cầu

- Docker Desktop đang chạy Linux containers.
- Docker Compose v2.
- Tối thiểu khoảng 8 GB RAM khả dụng để chạy toàn bộ microservice và AI.

### Cấu hình

Tạo file `.env` từ mẫu và điền secret cục bộ. Không commit `.env`, App Password,
JWT secret hoặc API key lên GitHub.

```powershell
Copy-Item .env.example .env
docker compose up -d --build
docker compose ps
```

Các biến tích hợp quan trọng:

- `GEMINI_API_KEY`, `GEMINI_MODEL`.
- `GOOGLE_CLIENT_ID`.
- `SMTP_USERNAME`, `SMTP_PASSWORD`, `MAIL_FROM` cho Gmail SMTP.
- `JWT_SECRET`, `SERVICE_TOKEN`, `BOOTSTRAP_TOKEN` nên dùng chuỗi ngẫu nhiên dài.
- `POSTGRES_PASSWORD` phải được thay khỏi giá trị mặc định trước khi triển khai.

### Địa chỉ local

| Thành phần | Địa chỉ |
|---|---|
| Web | <http://localhost:3000> |
| API Gateway | <http://localhost:8080> |
| AI Swagger | <http://localhost:8000/docs> |
| Adminer | <http://localhost:8081> |
| RabbitMQ Management | <http://localhost:15672> |

PostgreSQL, Adminer, RabbitMQ Management, AI và Gateway đang mở port để phát
triển local. Khi triển khai Internet, chỉ nên public `80/443` qua reverse proxy.

## Khởi tạo quản trị viên đầu tiên

Khi schema `auth` chưa có identity, dùng `BOOTSTRAP_TOKEN` để tạo Admin đúng một
lần:

```powershell
$headers = @{ "X-Bootstrap-Token" = $env:BOOTSTRAP_TOKEN }
$body = @{
  email = "admin@example.com"
  password = "replace-with-a-strong-password"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8080/api/v1/auth/bootstrap-admin `
  -Headers $headers `
  -ContentType "application/json" `
  -Body $body
```

Sau khi đăng nhập, Admin dùng màn hình **Nhân sự** để tạo tài khoản bác sĩ hoặc
lễ tân. Hệ thống không tự seed email, mật khẩu hoặc dữ liệu bệnh nhân giả.

## Huấn luyện và chạy AI cục bộ

Dataset và `best_model.pth` không được đưa lên Git. Nếu thiếu checkpoint,
`/predict` trả `503` thay vì tạo kết quả giả.

```powershell
Set-Location ai-service
python -m pip install -r requirements.txt
python scripts/validate_dataset.py --data ../SkinDisease
python training/train.py --data ../SkinDisease --model efficientnet_b0 --epochs 20
python training/evaluate.py --data ../SkinDisease --checkpoint models/best_model.pth
python rag/ingest.py --pdf ../SkinDisease/Huong-dan-chan-doan-dieu-tri-Da-lieu.pdf
uvicorn app.main:app --reload
```

## Kiểm thử

```powershell
# Regression build/unit/integration. Nếu máy không có Maven, script tự dùng
# container Maven Java 21. Browser E2E được ghi NOT_RUN và release gate chủ động
# trả mã khác 0 ở chế độ này vì bằng chứng phát hành chưa đầy đủ.
powershell -ExecutionPolicy Bypass -File tests/run-release-tests.ps1

# Chỉ dùng khi Docker Compose, tài khoản E2E và ảnh test thật đã sẵn sàng.
# Xem biến môi trường bắt buộc tại frontend/e2e/README.md.
$env:E2E_VIDEO = "on"
powershell -ExecutionPolicy Bypass -File tests/run-release-tests.ps1 -IncludeE2E
```

Bộ kiểm thử tài liệu gồm 81 test case, tập trung vào đặt lịch đồng thời, giữ
slot, đổi/hủy, hotline, check-in/no-show, WebSocket reconnect, chat, phân quyền
hồ sơ y tế, stored XSS và bằng chứng phát hành model AI. Lần chạy Playwright
live gần nhất có **5/5 case Pass**, không có case Fail hoặc Skip, trong 38,798
giây. Lượt chạy dùng PostgreSQL trong stack/volume E2E cô lập; stack và volume
được tự động xóa sau khi hoàn tất nên không ghi dữ liệu vào database local chính.
HTML report lưu 9 ảnh PNG và 5 video; log máy và artifact trình duyệt được giữ
cục bộ, không commit.

## Tài liệu

- [Đặc tả yêu cầu](docs/01-srs.md)
- [Kiến trúc và quyết định thiết kế](docs/02-architecture.md)
- [Đặc tả API](docs/03-api.md)
- [AI và RAG](docs/04-ai-rag.md)
- [Kế hoạch kiểm thử và triển khai](docs/05-delivery.md)
- [Triển khai production bằng Docker Compose](docs/production-deployment.md)
- [Quy ước và nguồn bằng chứng kiểm thử](docs/test-evidence.md)
- [Xác minh email và Gmail SMTP](docs/06-email-verification.md)
- [Model Card hiện tại](docs/model-card-scin-v1.md)
- [UML, Use Case, ERD và Deployment Diagram](docs/diagrams)

## Phạm vi

Đây là đồ án prototype phục vụ học tập và báo cáo, chưa phải thiết bị y tế hoặc
hệ thống được chứng nhận để sử dụng lâm sàng. Thanh toán trực tuyến, bảo hiểm,
quản lý kho và hóa đơn nằm ngoài phạm vi hiện tại; phí khám được thanh toán trực
tiếp tại phòng khám.
