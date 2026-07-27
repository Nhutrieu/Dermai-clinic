ALTER TABLE appointment_notifications
  ALTER COLUMN notification_type TYPE varchar(100);

INSERT INTO appointment_notifications(
  id, patient_identity_id, appointment_id, notification_type,
  title, body, created_at
)
SELECT
  ra.id,
  a.patient_identity_id,
  a.id,
  'MANUAL_REMINDER_' || ra.id,
  'Nhắc lịch khám từ lễ tân',
  'Bạn có lịch khám sắp tới. Vui lòng kiểm tra thời gian và đến đúng giờ.',
  ra.created_at
FROM reminder_actions ra
JOIN appointments a ON a.id = ra.appointment_id
WHERE ra.action_type = 'RESENT'
  AND NOT EXISTS (
    SELECT 1 FROM appointment_notifications n WHERE n.id = ra.id
  );
