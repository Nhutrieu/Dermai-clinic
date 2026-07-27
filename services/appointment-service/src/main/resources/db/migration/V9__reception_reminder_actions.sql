CREATE TABLE reminder_actions (
  id uuid PRIMARY KEY,
  appointment_id uuid NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
  receptionist_identity_id uuid NOT NULL,
  action_type varchar(30) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ix_reminder_action_appointment
  ON reminder_actions(appointment_id, created_at DESC);
