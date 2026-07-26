# Software Architecture Document

## 1. Bối cảnh

Frontend gọi một gateway duy nhất. Gateway xác thực access token, áp rate limit
và chuyển correlation ID. Dịch vụ nghiệp vụ sở hữu schema riêng; giao tiếp đồng
bộ qua REST cho truy vấn cần phản hồi ngay và RabbitMQ cho email/analytics.

## 2. Ranh giới

| Thành phần | Sở hữu dữ liệu | Lý do |
|---|---|---|
| Auth | identity, role, refresh token, OTP | Vòng đời và rủi ro bảo mật riêng |
| Clinic | patient, doctor, schedule, appointment, record, prescription | Giữ transaction lâm sàng nhất quán ở bản đầu |
| AI | model metadata, prediction, RAG chunks | Scale GPU/CPU độc lập, Python ecosystem |
| Notification | template, delivery attempt | Retry không làm chậm giao dịch |
| Analytics | projection KPI | Read model tối ưu dashboard |

Không dùng database chung xuyên service. Docker Compose tạo một PostgreSQL
instance cho môi trường dev nhưng mỗi service dùng database/user logic riêng.

## 3. Scheduling Engine

### Lọc bắt buộc

Slot ứng viên chỉ hợp lệ khi nằm trong ca làm, không chồng nghỉ phép, không chồng
lịch đã giữ/xác nhận, đúng chuyên môn và đủ thời lượng. PostgreSQL exclusion
constraint trên `(doctor_id, tstzrange(start_at,end_at))` là hàng rào cuối chống
race condition.

### Chấm điểm

Với mỗi ứng viên:

`score = 0.40*specialty + 0.25*earliness + 0.20*loadBalance + 0.10*continuity + 0.05*preference`

Mỗi thành phần chuẩn hóa [0,1]. `loadBalance = 1 - bookedMinutes/capacityMinutes`
trong ngày. Các trọng số là cấu hình và kết quả trả cả `reasons`, giúp quyết
định có thể giải thích. Không dùng thuộc tính nhạy cảm để xếp hạng.

Ví dụ: A đúng chuyên môn 1.0, sớm .8, tải .3, liên tục 1, ưu tiên .5, được
`.4 + .2 + .06 + .1 + .025 = .785`. B có tải .9 nhưng chưa từng khám:
`.4 + .18 + .18 + 0 + .025 = .785`; tie-break theo thời gian sớm rồi UUID.

### Đồng thời

`POST /appointments` mở transaction, khóa slot/advisory key, kiểm tra lại và
insert. Constraint xung đột bảo vệ ngay cả khi hai instance xử lý đồng thời.
Idempotency-Key ngăn tạo đôi khi client retry.

## 4. AI safety

Ảnh được lưu object storage bằng UUID, bỏ EXIF, mã hóa và không đưa vào log.
Prediction lưu top-k, model version, confidence và heatmap URI. Ngưỡng thấp
hiển thị “không chắc chắn”. Doctor phải tự nhập kết luận; không có nút sao chép
tự động AI thành final diagnosis.

RAG dùng retrieval trước generation, prompt giới hạn phạm vi, citations bắt
buộc và ngưỡng similarity. Nội dung về liều/thuốc bị policy layer từ chối.

## 5. Quyết định

- Java 21 + Spring Boot 3: LTS, validation/security/transaction mature.
- Python FastAPI: tích hợp PyTorch và xử lý ảnh tự nhiên.
- EfficientNet-B0 mặc định: cân bằng độ chính xác, tốc độ và kích thước. ResNet50
  là baseline dễ giải thích; ConvNeXt Tiny là challenger khi có GPU.
- RabbitMQ: routing/retry dễ vận hành cho quy mô đồ án.
- FAISS local cho demo; production nên dùng pgvector/Qdrant để HA và metadata filter.

