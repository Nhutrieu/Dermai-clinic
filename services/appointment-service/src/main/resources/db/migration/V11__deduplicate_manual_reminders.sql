DELETE FROM appointment_notifications n
USING (
  SELECT id, row_number() OVER (
    PARTITION BY appointment_id
    ORDER BY created_at DESC, id DESC
  ) AS position
  FROM appointment_notifications
  WHERE notification_type LIKE 'MANUAL_REMINDER_%'
) duplicates
WHERE n.id = duplicates.id
  AND duplicates.position > 1;
