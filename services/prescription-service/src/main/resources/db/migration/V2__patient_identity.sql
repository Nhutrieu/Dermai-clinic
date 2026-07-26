ALTER TABLE prescriptions ADD COLUMN IF NOT EXISTS patient_identity_id uuid;
CREATE INDEX IF NOT EXISTS ix_prescription_patient_identity ON prescriptions(patient_identity_id,signed_at DESC);
