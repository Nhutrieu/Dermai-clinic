# Kế hoạch thực hiện DermAI Clinic

> Phiên bản 2.0 · Đồng bộ với mã nguồn ngày 11/08/2026.

## 1. Định hướng đề tài

**Tên đề tài:** Hệ thống đặt lịch khám và hỗ trợ chẩn đoán y tế bằng trí tuệ
nhân tạo cho phòng khám da liễu.

Nghiệp vụ trung tâm là đặt lịch an toàn và điều phối bốn vai trò. Computer
Vision giúp Patient tham khảo ảnh da trước khi khám. AI không phải thiết bị y tế,
không thay bác sĩ, không tự tạo chẩn đoán cuối và không kê đơn.

### Mục tiêu chính

1. Đặt lịch không trùng khi nhiều người thao tác đồng thời.
2. Điều phối Patient, Receptionist, Doctor và Admin theo thời gian thực.
3. Huấn luyện/evaluate EfficientNet-B0 thật, có Top-3 và Grad-CAM.
4. Giải thích kết quả bằng retrieval từ tài liệu da liễu có kiểm soát.
5. Có test, model card, Docker và tài liệu đủ để tái lập/bảo vệ đồ án.

### Ngoài phạm vi

- Gói dịch vụ nhiều mức giá, thanh toán online và hóa đơn điện tử.
- Bảo hiểm, quản lý kho, SMS thương mại và kết nối bệnh viện.
- AI thay bác sĩ hoặc đưa ra phác đồ/đơn thuốc tự động.

Giá khám được Admin cấu hình theo Doctor, sao chụp vào appointment và thanh
toán trực tiếp tại phòng khám.

## 2. Kiến trúc đang sử dụng

```text
React + TypeScript + Vite + Nginx
                |
        Spring Cloud Gateway
                |
  Auth | Patient | Doctor | Appointment
  Medical Record | Prescription | Notification
                |
  PostgreSQL | RabbitMQ | Redis | FastAPI AI
                |
            Docker Compose
```

### Thành phần runtime

| Thành phần | Trách nhiệm |
|---|---|
| Gateway | JWT, RBAC headers, CORS, security headers và routing |
| Auth Service | Email OTP, Google OAuth, login, refresh/logout, nhân sự và avatar tài khoản |
| Patient Service | Hồ sơ, hotline relink, AI assessment và ảnh được chia sẻ |
| Doctor Service | Hồ sơ nghề nghiệp, avatar, giá, lịch làm và nghỉ phép |
| Appointment Service | Scheduling, hold/proposal, booking, trạng thái, realtime, chat, review, audit |
| Medical Record Service | Hồ sơ do Doctor ký; chức năng tùy chọn sau khám |
| Prescription Service | Đơn do Doctor ký; AI không được tạo đơn |
| Notification Service | Consumer RabbitMQ, chống lặp và Gmail SMTP |
| AI Service | EfficientNet-B0, Grad-CAM, RAG local và Gemini public chat |

Không có `Dashboard Service` riêng. Dashboard Admin tổng hợp từ các API runtime
hiện có. `services/clinic-service` là mã thử nghiệm, không nằm trong parent Maven
hoặc Docker Compose.

## 3. Công nghệ thực tế

- Frontend: React, TypeScript, Vite và CSS design system tự xây dựng; **không
  dùng TailwindCSS**.
- Backend: Java 21, Spring Boot 3.4, Spring Data JPA, Flyway.
- Gateway: Spring Cloud Gateway.
- Dữ liệu: PostgreSQL 16, 7 schema và 23 bảng runtime.
- Messaging: RabbitMQ với outbox; Redis có trong hạ tầng nhưng chưa dùng cho
  cache/rate limit.
- AI: Python, FastAPI, PyTorch, Torchvision, Pillow và OpenCV.
- RAG local: PDF theo trang, `chunks.json` và TF-IDF unigram/bigram; **không dùng
  LangChain/FAISS trong phiên bản hiện tại**.
- Hạ tầng: Docker Compose, Nginx, healthcheck và resource limit.

## 4. Nghiệp vụ đặt lịch đã chốt

- Booking window 60 ngày theo `Asia/Ho_Chi_Minh`.
- Ca làm định kỳ, nhiều khoảng trong ngày, nghỉ trưa, nghỉ phép và closure.
- Hold 5 phút; proposal của Receptionist/Admin 10 phút.
- Tối đa 3 lịch sắp tới cho Patient.
- Chặn Patient overlap và cùng Doctor hai lần trong ngày.
- `Idempotency-Key`, row lock và PostgreSQL exclusion constraint.
- Giá chốt bằng `consultation_fee_snapshot`.
- Patient tự đổi/hủy trong 30 phút đầu và trước khi xác nhận.
- Receptionist/Admin xác nhận, đặt hotline, reminder, check-in và no-show.
- Doctor bắt đầu/hoàn tất; hồ sơ/đơn không bắt buộc để hoàn tất.
- WebSocket báo thay đổi; client reconnect và fetch lại REST.
- Support conversation có thao tác claim nguyên tử.
- Trợ lý hỗ trợ tự động hướng dẫn quy trình và dùng RAG cho kiến thức da liễu
  chung; tra lịch bác sĩ bằng dữ liệu thật ở chế độ đọc-only. Thao tác lịch, tài
  khoản, khiếu nại và câu hỏi y khoa cá nhân luôn tự chuyển lễ tân, không tự thay
  đổi dữ liệu. Transcript Patient/AI/System và AI summary được giữ nguyên để lễ
  tân tiếp tục trong cùng conversation.
- Lễ tân đang phụ trách hoàn tất yêu cầu sau khi xử lý; transcript không bị xóa
  và lượt hỗ trợ mới của Patient quay lại AI Assistant trước.

### Trạng thái appointment

```text
HELD, PROPOSED, PENDING, ASSIGNED, CONFIRMED,
CHECKED_IN, IN_PROGRESS, COMPLETED,
FOLLOW_UP_REQUIRED, NO_SHOW, CANCELLED
```

### Recommendation

```text
score = 0.40*specialty
      + 0.25*earliness
      + 0.20*freeCapacity
      + 0.10*continuity
      + 0.05*preference
```

## 5. AI Computer Vision hiện tại

### Nhãn

`Acne`, `Candidiasis`, `Eczema`, `Lupus`, `Psoriasis`, `SkinCancer`, `Tinea`,
`Warts`.

Không dùng danh sách ví dụ cũ có Vitiligo/Herpes Zoster. `SkinCancer` chỉ là
nhãn nhóm trong dataset, không phải kết luận mô bệnh học.

### Model runtime

- EfficientNet-B0 pretrained ImageNet, fine-tune toàn bộ.
- Input 224×224, class-weighted Cross Entropy, AdamW, cosine scheduler và AMP.
- Model version: `efficientnet_b0-20260728T185742Z`.
- Checkpoint: `ai-service/models/best_model.pth` (không đưa lên Git).
- Output: Top-1, Top-3, confidence, uncertain, Grad-CAM, version và disclaimer.

| Tập | Ảnh | Accuracy | Macro F1 | Weighted F1 | Top-3 |
|---|---:|---:|---:|---:|---:|
| Test gốc cố định | 564 | 78,90% | 78,31% | 78,58% | 93,62% |
| SCIN external | 240 | 67,92% | 41,57% | 65,94% | 92,92% |

Patient Service lưu metadata và ảnh gốc của assessment để Patient xem lại/chia
sẻ; Grad-CAM không lưu. Doctor chỉ đọc ảnh khi Patient chia sẻ với đúng
appointment phụ trách. Response ảnh dùng `Cache-Control: no-store`.

### RAG và Gemini

- RAG local truy hồi theo trang từ tài liệu da liễu, trả tối đa ba ý tham khảo.
- Thiếu bằng chứng trả `has_evidence=false`; không tự bịa nội dung.
- Không nêu liều hoặc tên thuốc kê đơn trong guidance tự động.
- Gemini public chat chỉ trả kiến thức chăm sóc da chung, không nhận ảnh/PII.
- Trợ lý hỗ trợ dùng policy nội bộ để quyết định handoff. Gemini chỉ biên tập
  câu mẫu theo category, không nhận câu hỏi gốc của Patient.

## 6. Trạng thái thực hiện

### Đã hoàn thành ở mức đồ án

- Microservice runtime, Gateway, PostgreSQL migration và Docker Compose.
- Email OTP, Google OAuth, refresh rotation/logout và quản lý tài khoản nhân sự.
- Hồ sơ/ảnh đại diện Patient, Receptionist và Doctor.
- Booking safety, price snapshot, hotline, realtime, reminder, check-in/no-show.
- Claim support chat và xử lý đồng thời xác nhận lịch.
- Trợ lý hỗ trợ Patient và chuyển ngữ cảnh sang hộp thư lễ tân.
- UI bốn vai trò, responsive và design system.
- AI training/evaluation, SCIN supplement, Top-3, Grad-CAM, RAG và model card.
- SRS, architecture, API, UML/ERD, test case và tài liệu triển khai.

### Còn phải xác minh trước báo cáo

1. Chạy lại toàn bộ unit/integration/frontend/Python test trên commit báo cáo.
2. Chạy booking race bằng hai token Patient thật và lưu output/database evidence.
3. Chạy browser E2E cho booking, hotline, chat, check-in và AI share.
4. Kiểm tra accessibility ở 390, 768, 1024 và 1440 px.
5. Đo P50/P95 API booking và latency AI trên đúng máy demo.
6. Xác minh RabbitMQ → Notification → Gmail end-to-end và dead-letter.
7. Thử backup/restore PostgreSQL, kiểm tra dung lượng ổ đĩa.
8. Rate limit login, forgot-password, public chat và upload trước public hosting.
9. Thay toàn bộ secret mặc định, giới hạn CORS/WebSocket origin và dùng TLS.
10. Đánh giá AI bởi giảng viên/bác sĩ: class map, error analysis, domain shift,
    calibration và ảnh ngoài phân phối.

## 7. Kế hoạch đến ngày 20/09/2026

| Giai đoạn | Công việc | Đầu ra |
|---|---|---|
| 11–20/08 | Đồng bộ SRS/docs, chốt use case/diagram, sửa defect nghiêm trọng | Baseline tài liệu và release branch |
| 21–31/08 | Unit/integration, concurrency, realtime reconnect, browser E2E | Test report và bằng chứng |
| 01–07/09 | AI error analysis, latency, ảnh ngoài phân phối, model card | AI evaluation hoàn chỉnh |
| 08–12/09 | Backup/restore, Gmail, Docker clean install, security checklist | Release candidate |
| 13–16/09 | Viết báo cáo, slide, traceability và quay video dự phòng | Bộ hồ sơ bảo vệ |
| 17–19/09 | Rehearsal, kiểm tra máy/ổ đĩa/tài khoản, đóng băng code | Bản demo ổn định |
| 20/09 | Báo cáo | Demo và phản biện |

## 8. Chiến lược kiểm thử

| Lớp | Trọng tâm |
|---|---|
| Unit | Phone normalization, state transition, booking policy, score, auth và AI policy |
| Integration | Migration, repository constraint, service authorization, outbox và hotline relink |
| Concurrency | Hold/confirm cùng slot, xác nhận cùng lịch và claim cùng conversation |
| Realtime | Multi-tab, reconnect, slot, appointment, notification, avatar và chat |
| E2E | Đăng ký → đặt → xác nhận → check-in → khám → hoàn tất → review |
| AI | Validation ảnh, metric, confusion matrix, Grad-CAM, RAG refusal và external test |
| Security | Role/owner matrix, secret scan, upload fuzz, rate limit và log PII |
| Recovery | Restart container, backup/restore và disk-full preparation |

Không ghi một công cụ/metric đã chạy nếu chưa có log hoặc artifact chứng minh.

## 9. Kịch bản demo chính

1. Patient đăng ký OTP hoặc Google, hoàn thiện SĐT và hồ sơ.
2. Xem Doctor/giá, giữ slot, xác nhận và chứng minh giá snapshot.
3. Dùng Patient thứ hai chứng minh slot biến mất realtime và race chỉ một người
   thành công.
4. Receptionist nhận request, xác nhận, gửi reminder và check-in.
5. Receptionist tìm/tạo hồ sơ hotline và đặt hộ.
6. Patient chat; Receptionist claim; mở Receptionist thứ hai để chứng minh không
   trả lời chồng chéo.
7. Patient phân tích ảnh, xem Top-3/Grad-CAM/RAG, chia sẻ và đặt lịch.
8. Doctor xem đúng ảnh được chia sẻ, bắt đầu và hoàn tất không bắt buộc kê đơn.
9. Patient đánh giá; Admin duyệt và xem dashboard/audit.
10. Thử ảnh lỗi, model unavailable hoặc chatbot hỏi kê thuốc để chứng minh safety.

## 10. Sản phẩm bàn giao

- Source code, migration, test và scripts.
- Docker Compose, `.env.example`, hướng dẫn cài đặt và backup/restore.
- SRS Word/Markdown, architecture, API, AI/RAG guide và model card.
- PlantUML/PNG cho use case, activity, sequence, class, ERD, component và deployment.
- Dataset report, metric, confusion matrix, checkpoint checksum và Grad-CAM mẫu.
- Test report, traceability, slide, video dự phòng và hướng dẫn demo bốn vai trò.
