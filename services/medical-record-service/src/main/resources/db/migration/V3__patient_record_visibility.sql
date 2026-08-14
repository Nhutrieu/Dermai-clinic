CREATE TABLE IF NOT EXISTS patient_record_visibility (
    record_id uuid PRIMARY KEY REFERENCES medical_records(id),
    patient_identity_id uuid NOT NULL,
    hidden_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_patient_record_visibility_patient
    ON patient_record_visibility(patient_identity_id, hidden_at DESC);
