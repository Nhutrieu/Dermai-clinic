ALTER TABLE appointments
    ADD COLUMN IF NOT EXISTS checked_in_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_appointments_checked_in_at
    ON appointments (checked_in_at)
    WHERE checked_in_at IS NOT NULL;

-- An arrived patient still occupies the reserved slot. Keep CHECKED_IN inside
-- both exclusion constraints so another booking cannot overlap it.
ALTER TABLE appointments DROP CONSTRAINT IF EXISTS no_doctor_overlap;
ALTER TABLE appointments ADD CONSTRAINT no_doctor_overlap
    EXCLUDE USING gist (
        doctor_id WITH =,
        tstzrange(start_at, end_at, '[)') WITH &&
    )
    WHERE (doctor_id IS NOT NULL AND status IN ('HELD','PROPOSED','PENDING','ASSIGNED','CONFIRMED','CHECKED_IN','IN_PROGRESS'));

ALTER TABLE appointments DROP CONSTRAINT IF EXISTS no_patient_overlap;
ALTER TABLE appointments ADD CONSTRAINT no_patient_overlap
    EXCLUDE USING gist (
        patient_identity_id WITH =,
        tstzrange(start_at, end_at, '[)') WITH &&
    )
    WHERE (status IN ('HELD','PROPOSED','PENDING','ASSIGNED','CONFIRMED','CHECKED_IN','IN_PROGRESS'));
