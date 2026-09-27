CREATE TABLE ai_consent_events (
  id uuid PRIMARY KEY,
  patient_identity_id uuid NOT NULL,
  purpose varchar(80) NOT NULL,
  policy_version varchar(40) NOT NULL,
  granted_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE ai_assessments
  ADD COLUMN consent_event_id uuid REFERENCES ai_consent_events(id),
  ADD COLUMN image_retention_until timestamptz,
  ADD COLUMN deleted_at timestamptz;

UPDATE ai_assessments
SET image_retention_until = created_at + interval '180 days'
WHERE image_bytes IS NOT NULL;

CREATE INDEX ix_ai_assessments_image_retention
  ON ai_assessments(image_retention_until)
  WHERE image_bytes IS NOT NULL;

CREATE TABLE ai_access_audit_logs (
  id uuid PRIMARY KEY,
  assessment_id uuid,
  patient_identity_id uuid,
  actor_identity_id uuid NOT NULL,
  actor_role varchar(20) NOT NULL,
  action_type varchar(50) NOT NULL,
  source_ip varchar(64),
  user_agent varchar(500),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ix_ai_access_audit_actor_created
  ON ai_access_audit_logs(actor_identity_id, created_at DESC);

CREATE OR REPLACE FUNCTION reject_immutable_privacy_event_change()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'privacy consent and audit events are immutable';
END;
$$;

CREATE TRIGGER ai_consent_events_immutable
  BEFORE UPDATE OR DELETE ON ai_consent_events
  FOR EACH ROW EXECUTE FUNCTION reject_immutable_privacy_event_change();

CREATE TRIGGER ai_access_audit_logs_immutable
  BEFORE UPDATE OR DELETE ON ai_access_audit_logs
  FOR EACH ROW EXECUTE FUNCTION reject_immutable_privacy_event_change();
