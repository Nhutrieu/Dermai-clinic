CREATE TABLE reception_notifications (
  id uuid PRIMARY KEY,
  appointment_id uuid NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
  patient_identity_id uuid NOT NULL,
  notification_type varchar(100) NOT NULL,
  title varchar(160) NOT NULL,
  body varchar(500) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  read_at timestamptz,
  UNIQUE (appointment_id, notification_type)
);

CREATE INDEX ix_reception_notification_created
  ON reception_notifications(created_at DESC);