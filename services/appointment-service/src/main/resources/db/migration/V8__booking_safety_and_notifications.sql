ALTER TABLE appointments ADD COLUMN hold_expires_at timestamptz;

DROP INDEX IF EXISTS uq_patient_active_appointment;
ALTER TABLE appointments DROP CONSTRAINT IF EXISTS no_doctor_overlap;

ALTER TABLE appointments ADD CONSTRAINT no_doctor_overlap
  EXCLUDE USING gist (
    doctor_id WITH =,
    tstzrange(start_at, end_at, '[)') WITH &&
  )
  WHERE (doctor_id IS NOT NULL AND status IN ('HELD','PENDING','ASSIGNED','CONFIRMED','IN_PROGRESS'));

ALTER TABLE appointments ADD CONSTRAINT no_patient_overlap
  EXCLUDE USING gist (
    patient_identity_id WITH =,
    tstzrange(start_at, end_at, '[)') WITH &&
  )
  WHERE (status IN ('HELD','PENDING','ASSIGNED','CONFIRMED','IN_PROGRESS'));

CREATE INDEX ix_expiring_holds ON appointments(hold_expires_at)
  WHERE status = 'HELD';

CREATE TABLE clinic_closures (
  id uuid PRIMARY KEY,
  closure_date date NOT NULL UNIQUE,
  reason varchar(300) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE appointment_notifications (
  id uuid PRIMARY KEY,
  patient_identity_id uuid NOT NULL,
  appointment_id uuid REFERENCES appointments(id) ON DELETE CASCADE,
  notification_type varchar(50) NOT NULL,
  title varchar(160) NOT NULL,
  body varchar(500) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  read_at timestamptz,
  UNIQUE (appointment_id, notification_type)
);

CREATE INDEX ix_notification_patient ON appointment_notifications(patient_identity_id, created_at DESC);
