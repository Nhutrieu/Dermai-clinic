# Derm Clinic

**Hệ thống đặt lịch, quản lý phòng khám da liễu và hỗ trợ tham khảo ảnh da bằng AI.**

Derm Clinic kết hợp quy trình đặt lịch khám an toàn, điều phối lễ tân theo thời
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
- Xem lịch sắp tới và lịch sử trong mục **Lịch đã đặt**, nhận thông báo. Trợ lý
  hỗ trợ tự động trả lời thủ tục đơn giản; yêu cầu cần thao tác được chuyển sang
  lễ tân realtime.
- Phân tích ảnh da bằng AI, xem ba nhóm gợi ý, mức đồng thuận giữa các bộ mô hình,
  Grad-CAM minh họa và hướng dẫn tham khảo có nguồn từ RAG.
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
- Tải và thay ảnh đại diện JPG, PNG hoặc WebP, tối đa 2 MB.
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
- Trong 30 phút kể từ lúc đặt, bệnh nhân có thể tự đổi lịch `PENDING`/`ASSIGNED`
  và tự hủy lịch `PENDING`/`ASSIGNED`/`PENDING_CONFIRMATION`.
- Khi lễ tân đã xác nhận (`CONFIRMED`) hoặc hết thời hạn tự thao tác, bệnh nhân
  liên hệ lễ tân để đổi hoặc hủy lịch. Lịch đã cọc đang chờ xác nhận cũng cần
  lễ tân hỗ trợ nếu muốn đổi giờ.
- Slot, yêu cầu đặt lịch, thông báo, avatar và chat được đồng bộ bằng WebSocket.

## AI Computer Vision

API mặc định dùng **pipeline E/G/S biểu quyết năm fold**, phiên bản
`dermai-eight-esg-v1-20261108`. Mỗi fold dùng EfficientNet-B0, ConvNeXt-Tiny và
ResNet50; bộ chọn G hoạt động ở fold 0/3, specialist S ở fold 1/2, fold 4 dùng
ensemble E. B0 cũ được giữ cho bước kiểm tra ảnh ngoài phạm vi (OOD).

Phạm vi gồm tám nhóm: Acne, Candidiasis, Eczema, Lupus, Psoriasis, SkinCancer,
Tinea và Warts. Ảnh được kiểm tra chất lượng/OOD trước khi trả kết quả. Điểm
trên từng ảnh thể hiện **mức đồng thuận, không phải xác suất mắc bệnh**.
Grad-CAM minh họa từ B0 fold 0, không giải thích đầy đủ toàn bộ phép biểu quyết.
Xem [cấu hình phục vụ hiện tại](docs/KHOI_PHUC_BIEU_QUYET_NAM_FOLD_20261111.md).

Bản nghiên cứu trên **5.937 ảnh OOF** đạt **78,95% Accuracy, 77,73% Macro F1,
88,04% Recall SkinCancer**. Mỗi ảnh OOF được chấm bằng nhánh không dùng ảnh đó
để train; đây là kết quả phát triển, không phải điểm của bộ biểu quyết phục vụ.

Đánh giá hồi cứu API Docker ngày **10/11/2026** báo riêng số ảnh nhận và từ chối:

| Tập đánh giá | Tổng ảnh | Trả nhãn | Từ chối | Trả đúng | Độ đúng trên ảnh trả nhãn | Trả đúng / tổng ảnh |
|---|---:|---:|---:|---:|---:|---:|
| Test lịch sử sau rà trùng | 486 | 420 | 66 | 341 | 81,19% | 70,16% |
| SCIN sau rà trùng | 237 | 184 | 53 | 142 | 77,17% | 59,92% |

Các tập này đã được khảo sát trong lịch sử nghiên cứu, chưa phải test mù mới
độc lập theo bệnh nhân. Lượt đánh giá có một timeout được thử lại; bảng dùng
phản hồi cuối. [Báo cáo API và ma trận nhầm lẫn](ai-service/reports/application_evaluation_20261110/summary.md)
giải thích đầy đủ điều kiện và giới hạn. [Đối chứng ngày 13/11/2026](ai-service/reports/frozen_test_comparison_20261113/summary.md)
so sánh riêng bộ phân loại, không phải độ chính xác hoặc tốc độ toàn API.

[Bản giải trình pipeline](docs/GIAI_TRINH_PIPELINE_AI_CHO_THAY_20261108.md) mô tả
ensemble, bộ chọn dự đoán, specialist và đóng góp từng thành phần.

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
            └─ FastAPI AI Service — E/G/S năm fold / OOD / Grad-CAM / RAG

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
| AI | FastAPI, PyTorch, EfficientNet-B0 + ConvNeXt-Tiny + ResNet50, E/G/S, Grad-CAM, TF-IDF RAG và trợ lý Gemini |
| Hạ tầng | Docker Compose, healthcheck và giới hạn RAM từng container |

## Chạy bằng Docker

### Yêu cầu

- Docker Desktop đang chạy Linux containers.
- Docker Compose v2.
- Tối thiểu khoảng 8 GB RAM khả dụng để chạy toàn bộ microservice và AI.

### Cấu hình

Tạo file `.env` từ mẫu và điền secret cục bộ. Không commit `.env`, App Password,
JWT secret hoặc API key lên GitHub.

Trước khi khởi động, cần chuẩn bị đầy đủ package AI trong
`ai-service/models/research_pipeline/` và chỉ mục RAG trong `ai-service/rag-data/`.
GitHub chứa mã nguồn, manifest và báo cáo tổng hợp; checkpoint, tensor, dữ liệu
ảnh và chỉ mục RAG được giữ cục bộ. Chỉ clone repo chưa đủ để chạy tính năng AI.
Xem [chuẩn bị AI cục bộ](#chuẩn-bị-và-chạy-ai-cục-bộ).

```powershell
Copy-Item .env.example .env
docker compose up -d --build
docker compose ps
Invoke-RestMethod http://localhost:8000/health
```

AI sẵn sàng khi `/health` có `modelReady=true`, `ragReady=true`,
`modelVersion=dermai-eight-esg-v1-20261108` và
`aggregation=protected_fold_vote_v1`.

Các biến tích hợp quan trọng:

- `GEMINI_API_KEY`, `GEMINI_MODEL`.
- `GOOGLE_CLIENT_ID`.
- `SMTP_USERNAME`, `SMTP_PASSWORD`, `MAIL_FROM` cho Gmail SMTP.
- `JWT_SECRET`, `SERVICE_TOKEN`, `BOOTSTRAP_TOKEN` nên dùng chuỗi ngẫu nhiên dài.
- `POSTGRES_PASSWORD` phải được thay khỏi giá trị mặc định trước khi triển khai.
- `DATA_ENCRYPTION_KEY` bảo vệ ảnh assessment lưu trong database.
- `PAYOS_CLIENT_ID`, `PAYOS_API_KEY`, `PAYOS_CHECKSUM_KEY` và return/cancel URL
  cho thanh toán thật; `PAYOS_FAKE_MODE` chỉ dùng cho demo/kiểm thử.
- `PAYMENT_ALLOWED_RETURN_ORIGINS`: các origin frontend được phép nhận kết quả
  thanh toán, cách nhau bằng dấu phẩy. Khi dùng localhost cùng tunnel, thêm origin
  tunnel vào biến này. Liên kết cọc/hóa đơn mới quay về origin của trình duyệt tạo
  liên kết; yêu cầu không có `Origin` dùng return/cancel URL đã cấu hình. Liên kết
  PayOS cũ giữ URL ban đầu; `PAYOS_WEBHOOK_URL` cần truy cập được từ Internet.
- `AI_RESEARCH_MANIFEST_PATH`: đường dẫn manifest trong container; mặc định là
  `/models/research_pipeline/manifest.json`.

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

Sau khi đăng nhập, Admin dùng màn hình **Nhân sự** để tạo tài khoản bác sĩ,
lễ tân hoặc dược sĩ. Hệ thống không tự seed email, mật khẩu hoặc dữ liệu bệnh nhân
giả.

## Chuẩn bị và chạy AI cục bộ

Dùng Python 3.10 như môi trường Docker. Từ thư mục gốc dự án, tạo môi trường riêng:

```powershell
Set-Location ai-service
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Chuẩn bị package đúng phiên bản với `models/research_pipeline/manifest.json`
và toàn bộ tài sản được manifest tham chiếu. Nếu đã có checkpoint nghiên cứu gốc
cùng các báo cáo/tệp phụ thuộc, có thể đóng gói bằng lệnh sau; lệnh không train lại
và không ghi đè package đã có manifest:

```powershell
.\.venv\Scripts\python.exe training/export_research_runtime.py --output models/research_pipeline_export
```

Lệnh trên tạo một thư mục mới. Nếu chạy trực tiếp với package này, đặt
`$env:RESEARCH_MANIFEST_PATH = 'models/research_pipeline_export/manifest.json'`
trước khi khởi động API. Docker mặc định vẫn đọc `models/research_pipeline/`.

Không chạy lệnh export chỉ từ bản clone thiếu checkpoint. API kiểm tra SHA-256
của các tài sản trước khi nạp; package thiếu hoặc sai hash sẽ làm khởi động lỗi.
Xem [hướng dẫn package và cấu hình](docs/AP_DUNG_PIPELINE_AI_20261108.md).

Chuẩn bị chỉ mục RAG trong `ai-service/rag-data/`. Khi có tài liệu PDF nguồn tại
đường dẫn dưới đây, tạo chỉ mục bằng:

```powershell
.\.venv\Scripts\python.exe rag/ingest.py --pdf ../SkinDisease/Huong-dan-chan-doan-dieu-tri-Da-lieu.pdf --output rag-data
$env:RAG_INDEX_PATH = 'rag-data'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Mã train và đánh giá nằm trong [danh mục script](ai-service/DANH_MUC_TRAIN_MODEL.md).
Huấn luyện một B0 đơn không tạo ra package E/G/S năm fold đang phục vụ.

## Kiểm thử

Kiểm tra mã nguồn ngày **14/11/2026**, trước khi đẩy commit
[`b4bb3c08`](https://github.com/Nhutrieu/Dermai-clinic/commit/b4bb3c084525c4e2b9836075da7c865e0aaecf59):

| Phạm vi | Kết quả |
|---|---|
| Frontend unit test | 112 test đạt |
| Frontend build và kiểm tra kiểu E2E | Đạt |
| AI runtime và bộ đánh giá ứng dụng | 16 test đạt |
| Appointment, Doctor, Payment, Prescription service | 165 test đạt, không lỗi hoặc bỏ qua |
| Giao diện ảnh đại diện, lịch đã đặt, xóa kết quả AI và đổi lịch | 15 test Playwright đạt với API giả lập |

Lượt trên kiểm tra các phần thay đổi, chưa phải một lượt release suite đầy đủ
hoặc kiểm thử thanh toán PayOS thật. Bộ kiểm thử tổng thể:

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
bao gồm nhánh đặt cọc, hóa đơn và kho. [Lượt Playwright ngày 09/11/2026](docs/e2e-test-evidence-20261109.md)
đạt **9/9 PASS, 0 FAIL, 0 SKIP** trên stack PostgreSQL sạch, gồm hành trình đặt
lịch/cọc → khám → hóa đơn/thu tiền → cấp thuốc → review. PayOS dùng giả lập,
AI/RAG nạp thật; snapshot có `workingTreeDirty=true`. Kết quả Browser E2E này
không thay thế toàn bộ release suite hoặc kiểm thử PayOS thật. Artifact trình
duyệt được giữ cục bộ. Chạy lại riêng bộ E2E với database cô lập:

```powershell
powershell -ExecutionPolicy Bypass -File tests/run-isolated-e2e.ps1
```



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
- [AI service và cách chạy](ai-service/README.md)
- [Pipeline AI đang phục vụ](docs/KHOI_PHUC_BIEU_QUYET_NAM_FOLD_20261111.md)
- [Tổng hợp nghiên cứu AI](docs/ai-research-summary.md)
- [Tổng hợp chỉ số và giới hạn đánh giá](docs/TONG_HOP_CHI_SO_AI.md)
- [Model card B0 nền / cấu hình cũ](docs/model-card-scin-v1.md)
- [Tổng hợp các luồng thanh toán, hóa đơn và kho](docs/09-tong-hop-thay-doi-moi.md)
- [Tham chiếu schema](docs/database-schema-reference.md) và [hướng dẫn ERD](docs/database-erd-guide.md)
- [DBML ERD toàn hệ thống](database/dermai_erd.dbml)

## Phạm vi

Đây là đồ án prototype phục vụ học tập và báo cáo, chưa phải thiết bị y tế hoặc
hệ thống được chứng nhận để sử dụng lâm sàng. Bản hiện tại có đặt cọc và thanh
toán hóa đơn qua PayOS, thu tiền mặt tại quầy, hoàn cọc do lễ tân xử lý và quản lý
kho thuốc theo lô. Bảo hiểm, SMS thương mại, kết nối bệnh viện và hóa đơn điện tử
theo chuẩn thuế chưa được triển khai.
