# DermAI Clinic

Hệ thống hỗ trợ quản lý phòng khám da liễu và hỗ trợ quyết định lâm sàng bằng AI.
AI chỉ cung cấp thông tin tham khảo; chẩn đoán cuối cùng và đơn thuốc thuộc trách
nhiệm của bác sĩ.

## Kiến trúc

- `frontend`: React + TypeScript + Tailwind CSS.
- `services/gateway`: Spring Cloud Gateway, xác thực JWT tại biên.
- Các service nghiệp vụ độc lập: auth, patient, doctor, appointment, medical-record và prescription.
- `services/notification-service`: gửi thông báo bất đồng bộ.
- `services/analytics-service`: dashboard và chỉ số vận hành.
- `ai-service`: FastAPI, PyTorch classification, Grad-CAM và RAG có trích dẫn.
- PostgreSQL, Redis và RabbitMQ; toàn bộ được điều phối bằng Docker Compose.

Việc gom các aggregate giao dịch chặt vào `clinic-service` ở bản đầu là chủ ý:
đặt lịch, hồ sơ và đơn thuốc cần tính nhất quán cao. Ranh giới domain vẫn tách
theo package và event, cho phép tách thành service riêng khi tải hoặc đội ngũ tăng.

## Chạy nhanh

Yêu cầu: Docker Desktop và Docker Compose.

```bash
copy .env.example .env
docker compose up --build
```

Sau khi khởi động:

- Web: http://localhost:3000
- Gateway: http://localhost:8080
- AI API/Swagger: http://localhost:8000/docs
- MailHog: http://localhost:8025

Hệ thống không seed tài khoản hoặc dữ liệu nghiệp vụ mẫu. Hãy đăng ký tài khoản
Patient qua API/giao diện; các vai trò nhân viên phải được cấp bởi quy trình quản
trị. Trạng thái rỗng trên giao diện phản ánh đúng database chưa có dữ liệu.

## Khởi tạo quản trị viên và bác sĩ

Đặt `BOOTSTRAP_TOKEN` ngẫu nhiên trong `.env`. Khi database identity còn rỗng,
tạo Admin đầu tiên đúng một lần:

```powershell
$headers = @{ "X-Bootstrap-Token" = $env:BOOTSTRAP_TOKEN }
$body = @{ email = "email-that-cua-admin"; password = "mat-khau-tu-chon-du-manh" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8080/api/v1/auth/bootstrap-admin -Headers $headers -ContentType application/json -Body $body
```

Admin đăng nhập, gọi `POST /api/v1/auth/staff` với role `DOCTOR`, lấy
`identityId`, rồi gọi `POST /api/v1/doctors` để tạo hồ sơ chuyên môn tương ứng.
Không service nào tạo sẵn email, mật khẩu hoặc bác sĩ mẫu.

## AI

Dataset sẵn có có 14.529 tệp. Tập test hiện có 9 lớp; cấu hình mặc định dùng
8 lớp phù hợp phạm vi đồ án: Acne, Candidiasis, Eczema, Lupus, Psoriasis,
SkinCancer, Tinea (ringworm) và Warts. Lớp `SkinCancer` là nhóm nguy cơ, không
phải một chẩn đoán mô bệnh học.

```bash
cd ai-service
python -m pip install -r requirements.txt
python scripts/validate_dataset.py --data ../SkinDisease
python training/train.py --data ../SkinDisease --model efficientnet_b0 --epochs 20
python rag/ingest.py --pdf ../SkinDisease/Huong-dan-chan-doan-dieu-tri-Da-lieu.pdf
uvicorn app.main:app --reload
```

Nếu chưa có `models/best_model.pth`, endpoint `/predict` trả `503` thay vì tạo
kết quả giả.

## Tài liệu

- [SRS](docs/01-srs.md)
- [Kiến trúc và quyết định thiết kế](docs/02-architecture.md)
- [UML/ERD PlantUML](docs/diagrams)
- [API](docs/03-api.md)
- [AI và RAG](docs/04-ai-rag.md)
- [Roadmap, kiểm thử, triển khai](docs/05-delivery.md)
