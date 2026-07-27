ALTER TABLE appointments DROP CONSTRAINT IF EXISTS no_doctor_overlap;
ALTER TABLE appointments DROP CONSTRAINT IF EXISTS no_patient_overlap;

ALTER TABLE appointments ADD CONSTRAINT no_doctor_overlap
  EXCLUDE USING gist (
    doctor_id WITH =,
    tstzrange(start_at, end_at, '[)') WITH &&
  )
  WHERE (doctor_id IS NOT NULL AND status IN ('HELD','PROPOSED','PENDING','ASSIGNED','CONFIRMED','IN_PROGRESS'));

ALTER TABLE appointments ADD CONSTRAINT no_patient_overlap
  EXCLUDE USING gist (
    patient_identity_id WITH =,
    tstzrange(start_at, end_at, '[)') WITH &&
  )
  WHERE (status IN ('HELD','PROPOSED','PENDING','ASSIGNED','CONFIRMED','IN_PROGRESS'));

CREATE INDEX IF NOT EXISTS ix_expiring_proposals ON appointments(hold_expires_at)
  WHERE status = 'PROPOSED';
