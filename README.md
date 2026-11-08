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
- Chọn bác sĩ, ngày, khung giờ, nhập lý do, thanh toán cọc qua PayOS và theo dõi
  bước lễ tân xác nhận lịch. Có thể yêu cầu hoàn cọc cho lịch đủ điều kiện.
- Xem lịch sắp tới/lịch sử và nhận thông báo. Trợ lý hỗ trợ tự động trả lời thủ
  tục đơn giản; yêu cầu cần thao tác được chuyển sang lễ tân realtime.
- Phân tích ảnh da bằng AI, xem Top-3, confidence, Grad-CAM và hướng dẫn RAG.
- Lưu lịch sử assessment/ảnh, chủ động chia sẻ riêng cho bác sĩ phụ trách, xóa
  kết quả của mình và đánh giá sau buổi khám.
- Xem hóa đơn sau khám và thanh toán phần còn lại qua kênh online khi được mở.

### Lễ tân

- Nhận yêu cầu đặt lịch online theo thời gian thực.
- Xác nhận, đề nghị lịch khác, đổi hoặc hủy lịch theo yêu cầu bệnh nhân.
- Tra cứu bệnh nhân và đặt lịch qua hotline; số điện thoại là bắt buộc.
- Gửi nhắc lịch, check-in, điều phối hàng đợi và ghi nhận no-show.
- Nhận phụ trách cuộc trò chuyện để tránh nhiều lễ tân trả lời cùng lúc.
- Nhận yêu cầu đã được trợ lý phân loại kèm nội dung gốc của bệnh nhân.
- Xử lý hàng đợi hoàn cọc, lập hóa đơn sau khám, thu tiền mặt hoặc tạo liên kết
  thanh toán online; chuyển đơn đã thanh toán sang quầy dược.

### Bác sĩ

- Quản lý hồ sơ nghề nghiệp, ảnh đại diện, mô tả và lịch làm việc hằng tuần.
- Khai báo nghỉ phép, độ dài slot và theo dõi lịch được phân công.
- Xem lý do khám và kết quả AI mà bệnh nhân cho phép chia sẻ.
- Bắt đầu lượt khám, lập hồ sơ và đơn thuốc; xác nhận dịch vụ đã thực hiện trước
  khi hoàn tất, đánh dấu tái khám khi cần.

### Dược sĩ

- Xem đơn thuốc của hóa đơn đã thanh toán, nhập lô và xuất thuốc theo FEFO.
- Theo dõi tồn kho, nhật ký nhập/xuất, cảnh báo tồn thấp và lô sắp hết hạn.

### Quản trị viên

- Quản lý bệnh nhân, bác sĩ và tài khoản nhân sự.
- Cấu hình giá khám từng bác sĩ và ngày phòng khám đóng cửa.
- Kiểm duyệt đánh giá, xem audit và giám sát hộp thư hỗ trợ.
- Theo dõi dashboard vận hành và sửa trạng thái ca khám bị quên cập nhật.
- Quản lý danh mục dịch vụ, mức cọc, đối soát hóa đơn/doanh thu và xem kho thuốc.

## An toàn đặt lịch

- Chỉ cho đặt lịch trong 60 ngày tiếp theo.
- Slot được giữ tạm thời 5 phút; nhấn lại để nhả hoặc tự giải phóng khi hết hạn.
- Mỗi bệnh nhân có tối đa ba lịch sắp tới đang hoạt động.
- Không đặt hai bác sĩ trùng giờ hoặc cùng một bác sĩ hai lần trong cùng ngày.
- `Idempotency-Key`, khóa giao dịch và PostgreSQL exclusion constraint ngăn hai
  người xác nhận cùng một slot.
- Giá được lưu tại thời điểm đặt bằng `consultation_fee_snapshot`.
- Lịch online chuyển qua `PENDING_PAYMENT` rồi `PENDING_CONFIRMATION` sau khi
  cọc thành công; lễ tân mới xác nhận thành `CONFIRMED`.
- Bệnh nhân tự đổi lịch `PENDING`/`ASSIGNED` trong 30 phút đầu; tự hủy được cả
  lịch đã cọc/chờ xác nhận hoặc đã xác nhận trong thời hạn này. Sau đó liên hệ lễ tân.
- Slot, yêu cầu đặt lịch, thông báo, avatar và chat được đồng bộ bằng WebSocket.

## AI Computer Vision

API hiện dùng **EfficientNet-B0 đơn** (`efficientnet_b0-20260728T185742Z`),
trả Top-3, confidence, Grad-CAM và hướng dẫn RAG. Phạm vi gồm tám nhóm:
Acne, Candidiasis, Eczema, Lupus, Psoriasis, SkinCancer, Tinea và Warts.
Xem [AI và RAG](docs/04-ai-rag.md) và [model card hiện tại](docs/model-card-scin-v1.md).

Bản nghiên cứu ensemble đang giữ trên 5.937 ảnh OOF đạt **78,9456% Accuracy,
77,7287% Macro F1, 88,0355% Recall SkinCancer**. Đây là kết quả phát triển,
chưa phải kiểm chứng bệnh nhân mới; pipeline này chưa được triển khai vào API.
[Bản giải trình ngày 08/11/2026](docs/GIAI_TRINH_PIPELINE_AI_CHO_THAY_20261108.md)
mô tả ensemble, cổng chọn dự đoán, specialist và đóng góp từng thành phần.

Đọc [tổng hợp nghiên cứu](docs/ai-research-summary.md) để xem kết luận, giới hạn
và đường dẫn báo cáo gốc. Mã train và kết quả từng lượt ở `ai-service/training/`
và `ai-service/reports/`; [danh mục file train](ai-service/DANH_MUC_TRAIN_MODEL.md)
giải thích chức năng của từng chương trình.

## Kiến trúc hệ thống

```text
Browser
  └─ React + TypeScript + Vite + Nginx
       └─ Spring Cloud Gateway — JWT / RBAC / routing
            ├─ Auth Service
            ├─ Patient Service
            ├─ Doctor Service
            ├─ Appointment Service — booking engine / WebSocket
            ├─ Payment Service — PayOS / đặt cọc / hoàn cọc
            ├─ Medical Record Service
            ├─ Prescription Service — đơn thuốc / hóa đơn
            ├─ Inventory Service (FastAPI) — lô thuốc / cấp phát FEFO
            ├─ Notification Service — RabbitMQ / Gmail SMTP
            └─ FastAPI AI Service — EfficientNet-B0 / Grad-CAM / RAG

PostgreSQL 16 · Redis 7 · RabbitMQ 3.13 · Docker Compose
```

| Thành phần | Công nghệ / trách nhiệm |
|---|---|
| Frontend | React, TypeScript, Vite, CSS Design System và Nginx |
| Gateway | Spring Cloud Gateway, JWT, RBAC và định tuyến API |
| Backend | Java 21, Spring Boot 3.4, Spring Data JPA và Flyway |
| Kho thuốc | FastAPI, SQLAlchemy và PostgreSQL schema `pharmacy` |
| Dữ liệu | PostgreSQL 16 với 9 schema và 48 bảng nghiệp vụ |
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
- `DATA_ENCRYPTION_KEY` bảo vệ ảnh assessment lưu trong database.
- `PAYOS_CLIENT_ID`, `PAYOS_API_KEY`, `PAYOS_CHECKSUM_KEY` và return/cancel URL
  cho thanh toán thật; `PAYOS_FAKE_MODE` chỉ dùng cho demo/kiểm thử.

### Địa chỉ local

| Thành phần | Địa chỉ |
|---|---|
| Web | <http://localhost:3000> |
| API Gateway | <http://localhost:8080> |
| AI Swagger | <http://localhost:8000/docs> |
| Inventory Swagger | <http://localhost:8010/docs> |
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

Catalog gốc có 81 test case; [test case mở rộng](docs/07-test-cases-extended.md)
bao gồm nhánh đặt cọc, hóa đơn và kho. [Lượt Playwright ngày 06/09/2026](docs/e2e-test-evidence.md)
đạt **6/6 kịch bản Pass** trên stack PostgreSQL E2E cô lập. Bằng chứng này thuộc
revision cũ và không xác nhận các luồng thanh toán/kho hiện tại; cần chạy lại
release suite để nghiệm thu phiên bản mới. Artifact trình duyệt được giữ cục bộ.



## Tài liệu

Bắt đầu tại [mục lục tài liệu](docs/README.md).

- [Đặc tả yêu cầu](docs/01-srs.md)
- [Kiến trúc và quyết định thiết kế](docs/02-architecture.md)
- [Đặc tả API](docs/03-api.md)
- [AI và RAG](docs/04-ai-rag.md)
- [Kế hoạch kiểm thử và triển khai](docs/05-delivery.md)
- [Triển khai production bằng Docker Compose](docs/production-deployment.md)
- [Quy ước và nguồn bằng chứng kiểm thử](docs/test-evidence.md)
- [Xác minh email và Gmail SMTP](docs/06-email-verification.md)
- [Model Card hiện tại](docs/model-card-scin-v1.md)
- [Tổng hợp các luồng thanh toán, hóa đơn và kho](docs/09-tong-hop-thay-doi-moi.md)
- [Tham chiếu schema](docs/database-schema-reference.md) và [hướng dẫn ERD](docs/database-erd-guide.md)
- [DBML ERD toàn hệ thống](database/dermai_erd.dbml)

## Phạm vi

Đây là đồ án prototype phục vụ học tập và báo cáo, chưa phải thiết bị y tế hoặc
hệ thống được chứng nhận để sử dụng lâm sàng. Bản hiện tại có đặt cọc và thanh
toán hóa đơn qua PayOS, thu tiền mặt tại quầy, hoàn cọc do lễ tân xử lý và quản lý
kho thuốc theo lô. Bảo hiểm, SMS thương mại, kết nối bệnh viện và hóa đơn điện tử
theo chuẩn thuế chưa được triển khai.
