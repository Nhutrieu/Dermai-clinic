# Thiết kế API — DermAI Clinic

## 1. Quy ước chung

- Nghiệp vụ Spring Boot dùng base path `/api/v1`.
- AI đi qua Gateway với base path `/ai`.
- UUID dùng chuỗi chuẩn; thời gian dùng ISO-8601 UTC; lịch hiển thị theo
  `Asia/Ho_Chi_Minh`.
- Endpoint bảo vệ nhận `Authorization: Bearer <accessToken>`.
- Gateway tự tạo `X-User-Id` và `X-User-Role`; client không được tin cậy khi tự
  gửi hai header này.
- Các thao tác đặt/đổi/tái khám nhận `Idempotency-Key` khi được chỉ định.
- Lỗi nghiệp vụ chính dùng `ProblemDetail` với `status`, `detail` và `code`.
  Không phải mọi service hiện đã thêm `traceId` vào body lỗi.

## 2. Auth API

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| POST | `/api/v1/auth/register` | Public | Tạo identity Patient |
| POST | `/api/v1/auth/login` | Public | Nhận access token 15 phút và refresh token |
| POST | `/api/v1/auth/refresh` | Public | Thu hồi token cũ và rotate refresh token |
| POST | `/api/v1/auth/logout` | Public + refresh token | Thu hồi refresh token |
| POST | `/api/v1/auth/forgot-password` | Public | Gửi OTP nếu email tồn tại |
| POST | `/api/v1/auth/reset-password` | Public | Đặt lại mật khẩu bằng email + OTP |
| POST | `/api/v1/auth/bootstrap-admin` | Bootstrap token | Tạo Admin đầu tiên khi bảng identity rỗng |
| POST | `/api/v1/auth/staff` | Admin | Tạo Doctor/Receptionist/Admin |
| GET | `/api/v1/auth/patients/{identityId}/account` | Admin | Xem trạng thái tài khoản Patient |
| PATCH | `/api/v1/auth/patients/{identityId}/account` | Admin | Khóa hoặc mở khóa Patient |

### Login response

```json
{
  "accessToken": "eyJ...",
  "refreshToken": "...",
  "expiresIn": 900,
  "role": "PATIENT"
}
```

## 3. Patient API

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| POST | `/api/v1/patients/me` | Patient | Tạo hồ sơ hoặc nhận hồ sơ hotline cùng số điện thoại |
| GET | `/api/v1/patients/me` | Patient | Hồ sơ của tôi |
| PATCH | `/api/v1/patients/me` | Patient | Cập nhật hồ sơ |
| GET | `/api/v1/patients?query=&page=&size=` | Doctor/Receptionist/Admin | Tìm theo tên hoặc điện thoại |
| GET | `/api/v1/patients/{patientId}` | Doctor/Receptionist/Admin | Xem hồ sơ theo patient ID |
| GET | `/api/v1/patients/identity/{identityId}` | Receptionist/Admin | Tìm hồ sơ theo identity |
| POST | `/api/v1/patients/hotline` | Receptionist/Admin | Tạo hoặc lấy hồ sơ khách theo số điện thoại |

Số điện thoại nhận các dạng `+84`, `84`, `0084`, khoảng trắng, dấu chấm hoặc dấu
gạch và được chuẩn hóa về `0...`. Số không hợp lệ trả HTTP 400.

API `/patients/me/images` **chưa tồn tại**. Ảnh chẩn đoán hiện được gửi trực tiếp
đến `/ai/predict` và chưa được Patient Service lưu.

## 4. Doctor API

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/v1/doctors?specialty=` | Public | Danh sách bác sĩ; có thể lọc chuyên môn |
| GET | `/api/v1/doctors/me` | Doctor | Hồ sơ bác sĩ đăng nhập |
| PATCH | `/api/v1/doctors/me` | Doctor | Cập nhật hồ sơ nghề nghiệp |
| PATCH | `/api/v1/doctors/me/bio` | Doctor | Cập nhật mô tả công khai |
| POST | `/api/v1/doctors/me/avatar` | Doctor | Upload JPG/PNG/WebP tối đa 2 MB |
| GET | `/api/v1/doctors/{doctorId}/avatar` | Public | Đọc avatar |
| GET | `/api/v1/doctors/me/schedule` | Doctor | Lịch làm và nghỉ phép của tôi |
| POST | `/api/v1/doctors` | Admin | Tạo hồ sơ cho identity Doctor |
| PUT | `/api/v1/doctors/{doctorId}/schedule` | Doctor sở hữu/Admin | Thay toàn bộ lịch làm định kỳ |
| POST | `/api/v1/doctors/{doctorId}/leave` | Doctor sở hữu/Admin | Thêm nghỉ phép |
| DELETE | `/api/v1/doctors/{doctorId}/leave/{leaveId}` | Doctor sở hữu/Admin | Xóa nghỉ phép |

`/doctors/scheduling-data` là endpoint nội bộ phục vụ Appointment Service, không
phải API giao diện nên cần giữ giới hạn role.

## 5. Appointment API

### 5.1. Đọc lịch và availability

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/v1/appointments/mine` | Patient | Lịch của tôi, bỏ hold và lịch đã ẩn |
| GET | `/api/v1/appointments/{id}` | Chủ lịch/Doctor phụ trách/Receptionist/Admin | Chi tiết lịch |
| GET | `/api/v1/appointments/doctor/mine?from=&to=` | Doctor | Lịch đã tiếp nhận của bác sĩ |
| GET | `/api/v1/appointments/doctor/{doctorId}?from=&to=` | Doctor/Receptionist/Admin | Lịch theo bác sĩ |
| GET | `/api/v1/appointments/queue?from=&to=&status=` | Receptionist/Admin | Hàng đợi điều phối |
| GET | `/api/v1/appointments/availability?doctorId=&date=&durationMinutes=` | Authenticated | Slot và trạng thái |
| POST | `/api/v1/appointments/recommendations` | Patient/Receptionist/Doctor/Admin | Đề xuất có điểm và lý do |

### 5.2. Hold, đặt và chuyển trạng thái

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| POST | `/api/v1/appointments/holds` | Patient | Giữ slot 5 phút |
| POST | `/api/v1/appointments/holds/{id}/confirm` | Patient | Xác nhận hold thành `ASSIGNED` |
| DELETE | `/api/v1/appointments/holds/{id}` | Patient sở hữu | Nhả hold |
| POST | `/api/v1/appointments` | Patient/Receptionist | Tạo lịch trực tiếp sau kiểm tra availability |
| POST | `/api/v1/appointments/{id}/assign` | Receptionist/Admin | Phân bác sĩ/slot cho lịch `PENDING` |
| POST | `/api/v1/appointments/{id}/confirm` | Receptionist/Admin | Xác nhận lịch |
| POST | `/api/v1/appointments/{id}/start` | Doctor phụ trách | Bắt đầu khám |
| POST | `/api/v1/appointments/{id}/complete` | Doctor phụ trách | Hoàn thành khám |
| POST | `/api/v1/appointments/{id}/no-show` | Receptionist/Admin | Ghi nhận không đến sau 30 phút |
| POST | `/api/v1/appointments/{id}/cancel` | Patient sở hữu/Receptionist/Admin | Hủy có lý do |
| PATCH | `/api/v1/appointments/{id}/hide` | Patient sở hữu | Ẩn lịch đã hủy |
| POST | `/api/v1/appointments/{id}/reschedule` | Patient sở hữu/Receptionist | Hủy lịch cũ và tạo lịch mới |
| POST | `/api/v1/appointments/{id}/require-follow-up` | Doctor phụ trách | Yêu cầu tái khám |
| POST | `/api/v1/appointments/{id}/follow-up` | Patient sở hữu/Receptionist | Tạo lịch tái khám |

### 5.3. Đề nghị của lễ tân, thông báo và ngày nghỉ

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| POST | `/api/v1/appointments/proposals` | Receptionist/Admin | Gửi đề nghị lịch giữ 10 phút |
| GET | `/api/v1/appointments/proposals/mine` | Patient | Đề nghị còn hiệu lực |
| POST | `/api/v1/appointments/proposals/{id}/accept` | Patient sở hữu | Đồng ý đề nghị |
| POST | `/api/v1/appointments/proposals/{id}/decline` | Patient sở hữu | Từ chối và giải phóng slot |
| GET | `/api/v1/appointments/notifications/mine` | Patient | 50 thông báo mới nhất |
| PATCH | `/api/v1/appointments/notifications/{id}/read` | Patient sở hữu | Đánh dấu đã đọc |
| GET | `/api/v1/appointments/closures` | Doctor/Receptionist/Admin | Ngày phòng khám nghỉ |
| POST | `/api/v1/appointments/closures` | Admin | Thêm ngày nghỉ nếu chưa có lịch active |
| DELETE | `/api/v1/appointments/closures/{id}` | Admin | Xóa ngày nghỉ |
| GET | `/api/v1/appointments/reminders` | Receptionist/Admin | Lịch xác nhận hôm nay và ngày mai |
| POST | `/api/v1/appointments/{id}/reminder-actions` | Receptionist/Admin | Lưu `CALLED`, `RESENT` hoặc `UNREACHABLE` |

## 6. Chat hỗ trợ và đánh giá

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/v1/appointments/support` | Patient/Receptionist/Admin | Tin nhắn của tôi hoặc danh sách hội thoại |
| POST | `/api/v1/appointments/support` | Patient/Receptionist/Admin | Gửi tin nhắn |
| PATCH | `/api/v1/appointments/support/{id}/read` | Người nhận hợp lệ | Đánh dấu đã đọc |
| GET | `/api/v1/appointments/reviews/public` | Public | Tối đa 6 review đã duyệt |
| GET | `/api/v1/appointments/reviews/mine` | Patient | Review của tôi |
| PUT | `/api/v1/appointments/reviews/{appointmentId}` | Patient sở hữu | Đánh giá một lịch `COMPLETED` |
| GET | `/api/v1/appointments/reviews` | Admin | Toàn bộ review |
| PATCH | `/api/v1/appointments/reviews/{id}` | Admin | Chuyển `APPROVED` hoặc `HIDDEN` |

## 7. Medical record và prescription

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| POST | `/api/v1/medical-records` | Doctor phụ trách | Tạo hồ sơ cho lịch đang/đã khám |
| GET | `/api/v1/medical-records/{id}` | Owner/Doctor/Admin | Đọc hồ sơ theo ID |
| GET | `/api/v1/medical-records/appointment/{appointmentId}` | Doctor phụ trách/Admin | Hồ sơ theo lịch |
| GET | `/api/v1/medical-records/mine` | Patient | Hồ sơ của tôi |
| GET | `/api/v1/medical-records/doctor/mine` | Doctor | Hồ sơ do tôi ký |
| GET | `/api/v1/medical-records/patient/{patientId}` | Doctor/Admin | Hồ sơ theo bệnh nhân |
| POST | `/api/v1/prescriptions` | Doctor | Tạo và ký đơn gắn record |
| GET | `/api/v1/prescriptions/mine` | Patient | Đơn của tôi |
| GET | `/api/v1/prescriptions/patient/{patientId}` | Doctor/Admin | Đơn theo bệnh nhân |

Dashboard Admin hiện tổng hợp từ các API hiện có ở frontend; endpoint
`/dashboard/summary` chưa tồn tại trong runtime chính.

## 8. AI API

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| GET | `/ai/health` | Public | `modelReady`, `ragReady` |
| POST | `/ai/predict` | Authenticated | Multipart field `image`; inference + Grad-CAM |
| POST | `/ai/chat` | Authenticated | RAG extractive từ index local |
| POST | `/ai/public-chat` | Public | Gemini tư vấn kiến thức da liễu chung |

### Prediction response thực tế

```json
{
  "disease": "Eczema",
  "confidence": 0.82,
  "top3": [
    {"label": "Eczema", "probability": 0.82},
    {"label": "Psoriasis", "probability": 0.11},
    {"label": "Tinea", "probability": 0.04}
  ],
  "gradcam_image": "data:image/png;base64,...",
  "model_version": "efficientnet_b0-best",
  "uncertain": false,
  "disclaimer": "Kết quả chỉ nhằm hỗ trợ, không thay thế chẩn đoán của bác sĩ."
}
```

Response hiện không có `predictionId` và Grad-CAM không phải artifact URI lưu
lâu dài. Nếu chưa có checkpoint, `/ai/predict` trả HTTP 503.

## 9. Recommendation response

```json
{
  "items": [{
    "doctorId": "uuid",
    "doctorIdentityId": "uuid",
    "doctorName": "Bác sĩ Linh",
    "specialtyCode": "DA LIỄU - ĐIỀU TRỊ MỤN",
    "startAt": "2026-08-01T02:00:00Z",
    "endAt": "2026-08-01T02:30:00Z",
    "score": 0.785,
    "reasons": ["Đúng chuyên môn", "Bác sĩ từng theo dõi"]
  }],
  "algorithmVersion": "weighted-fair-v2",
  "timezone": "Asia/Ho_Chi_Minh"
}
```

## 10. WebSocket

Endpoint: `/api/v1/appointments/ws/slots`.

Payload là JSON event nhẹ có trường `type`; client không cập nhật database dựa
trực tiếp vào payload mà gọi lại REST API tương ứng. Production cần giới hạn
allowed origin thay vì `*`.
