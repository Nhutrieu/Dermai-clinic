# API Design

Base path `/api/v1`. JSON dùng ISO-8601 UTC, UUID, phân trang `page,size,sort`.
Lỗi theo RFC 9457 Problem Details và có `traceId`. API mutation hỗ trợ
`Idempotency-Key`.

| Method | Endpoint | Quyền | Mô tả |
|---|---|---|---|
| POST | `/auth/register` | Public | Đăng ký patient |
| POST | `/auth/login` | Public | Access + refresh token |
| POST | `/auth/refresh` | Public | Rotate refresh token |
| POST | `/auth/bootstrap-admin` | Bootstrap secret, một lần | Tạo Admin đầu tiên khi identity rỗng |
| POST | `/auth/staff` | Admin | Tạo identity Doctor/Receptionist/Admin |
| POST | `/auth/forgot-password` | Public | Gửi OTP |
| GET/PATCH | `/patients/me` | Patient | Hồ sơ của tôi |
| POST | `/patients/me/images` | Patient | Upload ảnh, trả object URI |
| GET | `/doctors` | Authenticated | Lọc chuyên môn |
| PUT | `/doctors/{id}/schedule` | Doctor/Admin | Lịch làm việc |
| POST | `/appointments/recommendations` | Patient/Receptionist | Gợi ý có giải thích |
| POST | `/appointments` | Patient/Receptionist | Giữ/đặt lịch |
| POST | `/appointments/{id}/confirm` | Receptionist | Xác nhận |
| POST | `/appointments/{id}/start` | Doctor | Bắt đầu khám |
| POST | `/appointments/{id}/cancel` | Patient/Receptionist | Hủy có lý do |
| POST | `/medical-records` | Doctor | Lưu hồ sơ |
| POST | `/prescriptions` | Doctor | Ký đơn |
| GET | `/dashboard/summary` | Admin | KPI |
| POST | `/ai/predict` | Doctor/Patient | Proxy tới AI |
| POST | `/ai/chat` | Authenticated | RAG có nguồn |

## Prediction response

```json
{
  "predictionId": "uuid",
  "disease": "Eczema",
  "confidence": 0.82,
  "top3": [{"label":"Eczema","probability":0.82}],
  "gradcamImage": "/api/v1/ai/artifacts/uuid.png",
  "modelVersion": "efficientnet_b0-2026.07",
  "disclaimer": "Kết quả chỉ nhằm hỗ trợ, không thay thế chẩn đoán của bác sĩ."
}
```

## Recommendation response

```json
{
  "items": [{
    "doctorId": "uuid",
    "startAt": "2026-08-01T02:00:00Z",
    "endAt": "2026-08-01T02:30:00Z",
    "score": 0.785,
    "reasons": ["Đúng chuyên môn", "Bác sĩ từng theo dõi bệnh nhân"]
  }]
}
```
