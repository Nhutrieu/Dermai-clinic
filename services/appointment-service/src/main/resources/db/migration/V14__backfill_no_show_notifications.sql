-- Ensure historical NO_SHOW appointments also produce an unread patient warning.
INSERT INTO appointment_notifications (
  id,
  patient_identity_id,
  appointment_id,
  notification_type,
  title,
  body,
  created_at,
  read_at
)
SELECT
  gen_random_uuid(),
  appointment.patient_identity_id,
  appointment.id,
  'NO_SHOW',
  'Cảnh báo: Bạn đã bỏ lỡ lịch khám',
  'Hệ thống ghi nhận bạn chưa đến theo lịch đã xác nhận. Nếu có nhầm lẫn hoặc cần đặt lại lịch, vui lòng liên hệ lễ tân qua chat hỗ trợ hoặc hotline 0352 790 904.',
  COALESCE(appointment.updated_at, CURRENT_TIMESTAMP),
  NULL
FROM appointments AS appointment
WHERE appointment.status = 'NO_SHOW'
  AND NOT EXISTS (
    SELECT 1
    FROM appointment_notifications AS notification
    WHERE notification.appointment_id = appointment.id
      AND notification.notification_type = 'NO_SHOW'
  );
