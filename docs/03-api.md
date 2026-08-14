# Thiết kế API — DermAI Clinic

> Cập nhật theo mã nguồn runtime ngày 11/08/2026. Base path nghiệp vụ là
> `/api/v1`; AI đi qua Gateway với base path `/ai`.

## 1. Quy ước chung

- UUID dùng chuỗi chuẩn; thời gian dùng ISO-8601 UTC và hiển thị theo
  `Asia/Ho_Chi_Minh`.
- Endpoint bảo vệ nhận `Authorization: Bearer <accessToken>`.
- Gateway xác thực JWT rồi tạo `X-User-Id` và `X-User-Role`; không tin hai header
  này khi client tự gửi.
- Access token có hiệu lực 15 phút. Refresh token có hiệu lực 14 ngày, được
  rotate khi refresh và bị thu hồi khi logout.
- Các thao tác đặt, đổi và tái khám hỗ trợ `Idempotency-Key` để chống tạo đôi
  khi client retry.
- Lỗi nghiệp vụ chính trả `ProblemDetail` với HTTP status, `detail` và `code`.
- Endpoint nội bộ nhạy cảm dùng `X-Service-Token`.

## 2. Auth API

### 2.1. Đăng ký, đăng nhập và khôi phục

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| POST | `/api/v1/auth/register` | Public | Tạo identity Patient và khởi tạo bước xác minh email |
| POST | `/api/v1/auth/verification/send` | Public | Gửi lại mã xác minh email |
| POST | `/api/v1/auth/verification/confirm` | Public | Xác minh email bằng OTP |
| POST | `/api/v1/auth/login` | Public | Nhận access token và refresh token |
| GET | `/api/v1/auth/google/config` | Public | Trả trạng thái Google Login và client ID công khai |
| POST | `/api/v1/auth/google` | Public | Xác minh Google credential và đăng nhập/đăng ký Patient |
| POST | `/api/v1/auth/refresh` | Public | Thu hồi token cũ và rotate refresh token |
| POST | `/api/v1/auth/logout` | Public + refresh token | Thu hồi refresh token |
| POST | `/api/v1/auth/forgot-password` | Public | Gửi OTP nếu email tồn tại |
| POST | `/api/v1/auth/reset-password` | Public | Đặt lại mật khẩu bằng email, OTP và mật khẩu mới |

Frontend tự thử refresh đúng một lần khi request trả 401. Nếu refresh thất bại,
session bị xóa và người dùng quay về màn hình đăng nhập.

### 2.2. Hồ sơ tài khoản và quản trị nhân sự

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/v1/auth/me` | Authenticated | Thông tin tài khoản đang đăng nhập |
| PATCH | `/api/v1/auth/me/profile` | Authenticated | Cập nhật họ tên tài khoản |
| POST | `/api/v1/auth/me/avatar` | Authenticated | Upload avatar tài khoản |
| GET | `/api/v1/auth/me/avatar` | Authenticated | Đọc avatar của tôi |
| GET | `/api/v1/auth/accounts/{id}/avatar` | Staff | Đọc avatar tài khoản để hiển thị quản trị/hỗ trợ |
| POST | `/api/v1/auth/staff` | Admin | Tạo Doctor, Receptionist hoặc Admin |
| GET | `/api/v1/auth/staff?role=` | Admin | Danh sách tài khoản nhân sự theo vai trò |
| GET | `/api/v1/auth/staff/directory` | Staff | Danh bạ nhân sự tối thiểu phục vụ giao diện |
| PATCH | `/api/v1/auth/staff/{id}/account` | Admin | Khóa hoặc mở tài khoản nhân sự |
| PATCH | `/api/v1/auth/staff/{id}/password` | Admin | Đặt lại mật khẩu nhân sự |
| PATCH | `/api/v1/auth/staff/{id}/profile` | Admin | Cập nhật họ tên nhân sự |
| GET | `/api/v1/auth/staff/{id}/events` | Admin | Nhật ký thao tác tài khoản nhân sự |
| GET | `/api/v1/auth/patients/{id}/account` | Admin | Xem trạng thái tài khoản Patient |
| PATCH | `/api/v1/auth/patients/{id}/account` | Admin | Khóa hoặc mở tài khoản Patient |
| POST | `/api/v1/auth/bootstrap-admin` | Bootstrap token | Tạo Admin đầu tiên khi bảng identity rỗng |

## 3. Patient API

### 3.1. Hồ sơ bệnh nhân

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| POST | `/api/v1/patients/me` | Patient | Tạo hồ sơ hoặc nhận lại hồ sơ hotline cùng số điện thoại |
| GET | `/api/v1/patients/me` | Patient | Hồ sơ của tôi |
| PATCH | `/api/v1/patients/me` | Patient | Cập nhật hồ sơ |
| GET | `/api/v1/patients?query=&page=&size=` | Doctor/Receptionist/Admin | Tìm theo tên hoặc số điện thoại |
| GET | `/api/v1/patients/{patientId}` | Doctor/Receptionist/Admin | Xem hồ sơ theo patient ID |
| GET | `/api/v1/patients/identity/{identityId}` | Receptionist/Admin | Tìm hồ sơ theo identity |
| POST | `/api/v1/patients/hotline` | Receptionist/Admin | Tạo hoặc lấy hồ sơ khách theo số điện thoại |

Số điện thoại nhận các dạng `+84`, `84`, `0084`, khoảng trắng, dấu chấm hoặc dấu
gạch và được chuẩn hóa về `0...`. Số không hợp lệ trả HTTP 400.

### 3.2. Lịch sử kiểm tra da AI

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/v1/patients/me/ai-assessments` | Patient | Lịch sử kết quả của tôi |
| POST | `/api/v1/patients/me/ai-assessments` | Patient | Lưu metadata kết quả inference |
| PUT | `/api/v1/patients/me/ai-assessments/{id}/image` | Patient sở hữu | Lưu ảnh gốc của lần kiểm tra |
| GET | `/api/v1/patients/me/ai-assessments/{id}/image` | Patient sở hữu | Đọc ảnh gốc của tôi |
| PATCH | `/api/v1/patients/me/ai-assessments/{id}/sharing` | Patient sở hữu | Bật/tắt chia sẻ với lịch khám |
| GET | `/api/v1/patients/appointments/{appointmentId}/shared-ai-assessment` | Doctor phụ trách | Đọc metadata đã được Patient chia sẻ |
| GET | `/api/v1/patients/appointments/{appointmentId}/shared-ai-assessment/image` | Doctor phụ trách | Đọc ảnh đã chia sẻ |
| DELETE | `/api/v1/patients/me/ai-assessments/{id}` | Patient sở hữu | Xóa kết quả và ảnh khỏi lịch sử |

Ảnh gốc được lưu dạng BLOB trong Patient Service và endpoint ảnh trả
`Cache-Control: no-store`. Doctor chỉ truy cập khi Patient đã chia sẻ và Doctor
đúng là người phụ trách appointment. Grad-CAM không được lưu lâu dài.

## 4. Doctor API

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/v1/doctors?specialty=` | Public | Danh sách bác sĩ, có thể lọc chuyên môn |
| GET | `/api/v1/doctors/me` | Doctor | Hồ sơ bác sĩ đăng nhập |
| PATCH | `/api/v1/doctors/me` | Doctor | Cập nhật hồ sơ nghề nghiệp |
| PATCH | `/api/v1/doctors/me/bio` | Doctor | Cập nhật mô tả công khai |
| POST | `/api/v1/doctors/me/avatar` | Doctor | Upload JPG/PNG/WebP tối đa 2 MB |
| GET | `/api/v1/doctors/{doctorId}/avatar` | Public | Đọc avatar bác sĩ |
| GET | `/api/v1/doctors/me/schedule` | Doctor | Lịch làm và nghỉ phép của tôi |
| GET | `/api/v1/doctors/scheduling-data` | Authenticated theo role | Dữ liệu bác sĩ phục vụ Scheduling Engine |
| POST | `/api/v1/doctors` | Admin | Tạo hồ sơ cho identity Doctor |
| PATCH | `/api/v1/doctors/{doctorId}/consultation-fee` | Admin | Cập nhật giá khám cơ bản |
| PUT | `/api/v1/doctors/{doctorId}/schedule` | Doctor sở hữu/Admin | Thay toàn bộ lịch làm định kỳ |
| POST | `/api/v1/doctors/{doctorId}/leave` | Doctor sở hữu/Admin | Thêm nghỉ phép |
| DELETE | `/api/v1/doctors/{doctorId}/leave/{leaveId}` | Doctor sở hữu/Admin | Xóa nghỉ phép |

Doctor không tự sửa giá khám. Appointment Service chụp giá hiện tại thành
`consultation_fee_snapshot` khi lịch được tạo hoặc phân công.

## 5. Appointment API

### 5.1. Đọc lịch và availability

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/v1/appointments/mine` | Patient | Lịch của tôi, không gồm hold và lịch đã ẩn |
| GET | `/api/v1/appointments/{id}` | Chủ lịch/Doctor phụ trách/Receptionist/Admin | Chi tiết lịch |
| GET | `/api/v1/appointments/doctor/mine?from=&to=` | Doctor | Lịch đã tiếp nhận của bác sĩ |
| GET | `/api/v1/appointments/doctor/{doctorId}?from=&to=` | Doctor/Receptionist/Admin | Lịch theo bác sĩ |
| GET | `/api/v1/appointments/queue?from=&to=&status=` | Receptionist/Admin | Hàng đợi điều phối |
| GET | `/api/v1/appointments/availability?doctorId=&date=&durationMinutes=` | Authenticated | Slot và trạng thái khả dụng |
| POST | `/api/v1/appointments/recommendations` | Patient/Receptionist/Doctor/Admin | Đề xuất slot có điểm và lý do |
| GET | `/api/v1/appointments/staff-actions?actorIdentityId=` | Admin | Nhật ký thao tác lịch gần đây của nhân sự |

### 5.2. Giữ slot, đặt và chuyển trạng thái

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| POST | `/api/v1/appointments/holds` | Patient | Giữ slot 5 phút và snapshot giá |
| POST | `/api/v1/appointments/holds/{id}/confirm` | Patient | Xác nhận hold thành `ASSIGNED` |
| DELETE | `/api/v1/appointments/holds/{id}` | Patient sở hữu | Nhả hold |
| POST | `/api/v1/appointments` | Patient/Receptionist/Admin | Tạo lịch trực tiếp sau kiểm tra availability |
| POST | `/api/v1/appointments/{id}/assign` | Receptionist/Admin | Phân bác sĩ/slot và cập nhật snapshot giá |
| POST | `/api/v1/appointments/{id}/confirm` | Receptionist/Admin | Xác nhận lịch |
| POST | `/api/v1/appointments/{id}/check-in` | Receptionist/Admin | Tiếp nhận bệnh nhân tại phòng khám |
| POST | `/api/v1/appointments/{id}/start` | Doctor phụ trách | Bắt đầu lượt khám |
| POST | `/api/v1/appointments/{id}/complete` | Doctor phụ trách hoặc Receptionist/Admin | Hoàn tất; nhân viên chỉ sửa ca `IN_PROGRESS` bị treo quá lâu |
| POST | `/api/v1/appointments/{id}/no-show` | Receptionist/Admin | Ghi nhận không đến sau ngưỡng nghiệp vụ |
| POST | `/api/v1/appointments/{id}/cancel` | Patient sở hữu/Receptionist/Admin | Hủy có lý do |
| PATCH | `/api/v1/appointments/{id}/hide` | Patient sở hữu | Ẩn lịch đã hủy khỏi danh sách cá nhân |
| POST | `/api/v1/appointments/{id}/reschedule` | Patient sở hữu/Receptionist/Admin | Hủy lịch cũ và tạo lịch mới |
| POST | `/api/v1/appointments/{id}/require-follow-up` | Doctor phụ trách | Yêu cầu tái khám |
| POST | `/api/v1/appointments/{id}/follow-up` | Patient sở hữu/Receptionist/Admin | Tạo lịch tái khám |

Patient chỉ tự đổi/hủy lịch ở trạng thái `PENDING` hoặc `ASSIGNED`, trong 30 phút
từ lúc đặt và trước khi lễ tân xác nhận. Sau đó phải liên hệ hỗ trợ. Patient có
tối đa ba lịch active, không được trùng thời gian và không đặt cùng Doctor hai lần
trong cùng ngày. Nhân viên được phép vượt giới hạn ba lịch khi thật sự cần nhưng
vẫn không thể tạo hai lịch chiếm cùng một slot.

### 5.3. Đề nghị lịch, thông báo, nhắc lịch và ngày nghỉ

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

### 6.1. Chat hỗ trợ

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/v1/appointments/support` | Patient/Receptionist/Admin | Tin nhắn cá nhân hoặc hội thoại được chọn |
| GET | `/api/v1/appointments/support/conversations` | Receptionist/Admin | Danh sách hội thoại và người đang phụ trách |
| POST | `/api/v1/appointments/support/assistant` | Patient | Lưu lượt chat, phân loại intent, tra cứu read-only và tự chuyển lễ tân khi cần |
| POST | `/api/v1/appointments/support/conversations/{patientIdentityId}/claim` | Receptionist | Nhận cuộc trò chuyện bằng thao tác nguyên tử |
| DELETE | `/api/v1/appointments/support/conversations/{patientIdentityId}/claim` | Receptionist đang phụ trách | Trả cuộc trò chuyện |
| POST | `/api/v1/appointments/support/conversations/{patientIdentityId}/resolve` | Receptionist đang phụ trách | Hoàn tất hỗ trợ và đưa yêu cầu tiếp theo về AI-first |
| POST | `/api/v1/appointments/support` | Patient/Receptionist đã nhận | Gửi tin nhắn |
| PATCH | `/api/v1/appointments/support/{id}/read` | Người nhận hợp lệ | Đánh dấu đã đọc |

Admin được xem/giám sát nhưng không gửi tin. Nếu hai lễ tân cùng nhận, chỉ một
người thành công; người còn lại nhận HTTP 409 và danh sách được cập nhật realtime.
Receptionist chỉ nhận các conversation ở `WAITING_RECEPTIONIST` hoặc `ASSIGNED`;
conversation `AI_ACTIVE` vẫn thuộc tầng AI. Khi bàn giao, endpoint trả cùng lịch
sử `PATIENT / AI / SYSTEM` và conversation chứa `aiSummary`, `lastIntent`,
`lastIntentConfidence`, `escalationReason`.

### 6.2. Đánh giá phòng khám

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/v1/appointments/reviews/public` | Public | Tối đa sáu review đã duyệt |
| GET | `/api/v1/appointments/reviews/mine` | Patient | Review của tôi |
| PUT | `/api/v1/appointments/reviews/{appointmentId}` | Patient sở hữu | Đánh giá một lịch `COMPLETED`, mỗi lịch một lần |
| GET | `/api/v1/appointments/reviews` | Admin | Toàn bộ review |
| PATCH | `/api/v1/appointments/reviews/{id}` | Admin | Chuyển `APPROVED` hoặc `HIDDEN` |

## 7. Medical Record và Prescription

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

Việc tạo hồ sơ và kê đơn là chức năng bổ trợ, không phải điều kiện bắt buộc để
Doctor hoàn tất một lượt khám. Hệ thống hiện không có thanh toán, hóa đơn hoặc
chi phí phát sinh.

## 8. AI API

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| GET | `/ai/health` | Public | Trả `modelReady` và `ragReady` |
| POST | `/ai/predict` | Patient | Inference ảnh, Top-3, Grad-CAM và hướng dẫn RAG |
| POST | `/ai/chat` | Authenticated | RAG extractive từ index local |
| POST | `/ai/public-chat` | Public | Gemini tư vấn kiến thức da liễu chung |
| POST | `/ai/support-chat` | Patient | Trả FAQ/quy trình, tra cứu RAG an toàn hoặc yêu cầu chuyển lễ tân |

Ví dụ rút gọn của `/ai/predict`:

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
  "model_version": "efficientnet_b0-20260728T185742Z",
  "uncertain": false,
  "disclaimer": "Kết quả chỉ nhằm hỗ trợ, không thay thế chẩn đoán của bác sĩ.",
  "guidance": {
    "title": "Thông tin tham khảo về chàm và viêm da cơ địa",
    "answer": "• Ý xử trí tham khảo thứ nhất...",
    "citations": [{"source": "Huong-dan-chan-doan-dieu-tri-Da-lieu.pdf", "page": 115}],
    "has_evidence": true
  }
}
```

Response không có `predictionId`; Grad-CAM là data URL tạm thời. Sau inference,
frontend gọi Patient API để lưu metadata và ảnh gốc. `guidance` tối đa ba ý,
không chứa liều hoặc tên thuốc kê đơn. Thiếu checkpoint trả HTTP 503; RAG chưa
sẵn sàng trả `has_evidence=false` thay vì tự sinh nội dung không có nguồn.

### Support assistant response

```json
{
  "answer": "Tôi chưa thể xử lý yêu cầu đổi lịch trực tiếp...",
  "category": "RESCHEDULE_APPOINTMENT",
  "requires_handoff": true,
  "handoff_summary": "Bệnh nhân yêu cầu hỗ trợ đổi lịch.",
  "automated": true
}
```

Endpoint không tự gọi Appointment API. Câu hỏi kiến thức da liễu chung chỉ được
trả lời khi RAG local tìm thấy nội dung an toàn; câu hỏi cá nhân, kê đơn hoặc
thiếu bằng chứng sẽ đánh dấu cần người thật. Endpoint nội bộ này chỉ phân loại và
biên tập câu trả lời; Appointment Service mới quyết định chuyển, lưu transcript
và tra lịch thật.

Response rút gọn của `/api/v1/appointments/support/assistant`:

```json
{
  "answer": "Mình sẽ chuyển cuộc trò chuyện cho bộ phận lễ tân hỗ trợ tiếp.",
  "intent": "CANCEL_APPOINTMENT",
  "intentConfidence": 0.9,
  "escalated": true,
  "conversationStatus": "WAITING_RECEPTIONIST",
  "escalationReason": "MANDATORY_CANCEL_APPOINTMENT"
}
```

Luồng tự chuyển không yêu cầu Patient xác nhận và không tạo chat mới. Yêu cầu
gặp lễ tân lần đầu được AI hỏi vấn đề; nếu Patient tiếp tục yêu cầu hoặc hai lượt
liên tiếp không giải quyết được thì tự chuyển. WebSocket `CHAT_CHANGED` làm mới
hộp thư lễ tân và cuộc trò chuyện của Patient.

## 9. Recommendation response

```json
{
  "items": [{
    "doctorId": "uuid",
    "doctorIdentityId": "uuid",
    "doctorName": "BS. Linh",
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

Event chỉ báo loại thay đổi về slot, appointment, chat, notification hoặc Doctor
profile. Client nhận event rồi tải lại dữ liệu qua REST; WebSocket không thay thế
kiểm tra quyền và ràng buộc database. Client có reconnect và refetch sau khi kết
nối lại. Production phải giới hạn allowed origin thay cho `*`.

Dashboard Admin tổng hợp từ các API hiện có; runtime chính chưa có endpoint
`/dashboard/summary` riêng.
