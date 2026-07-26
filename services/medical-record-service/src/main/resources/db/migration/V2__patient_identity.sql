ALTER TABLE medical_records ADD COLUMN IF NOT EXISTS patient_identity_id uuid;
CREATE INDEX IF NOT EXISTS ix_record_patient_identity ON medical_records(patient_identity_id,signed_at DESC);
