INSERT INTO reception_notifications (
  id,
  appointment_id,
  patient_identity_id,
  notification_type,
  title,
  body,
  created_at
)
SELECT
  gen_random_uuid(),
  id,
  patient_identity_id,
  'PAYMENT_CANCELLED_BY_PATIENT',
  'Bệnh nhân đã hủy trước khi thanh toán',
  'Lịch ' || to_char(start_at AT TIME ZONE 'Asia/Ho_Chi_Minh', 'HH24:MI "ngày" DD/MM/YYYY') || ' đã được hủy. Không phát sinh hoàn tiền và khung giờ đã được trả lại.',
  COALESCE(updated_at, now())
FROM appointments
WHERE cancel_reason = 'PAYMENT_CANCELLED_BY_PATIENT'
ON CONFLICT (appointment_id, notification_type) DO NOTHING;