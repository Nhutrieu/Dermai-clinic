ALTER TABLE ai_assessments
  ADD COLUMN appointment_id uuid,
  ADD COLUMN image_content_type varchar(80),
  ADD COLUMN image_bytes bytea;

CREATE UNIQUE INDEX ux_ai_assessments_shared_appointment
  ON ai_assessments(appointment_id)
  WHERE appointment_id IS NOT NULL AND shared_with_doctor = true;
