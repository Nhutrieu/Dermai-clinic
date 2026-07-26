CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE TABLE appointments(id uuid PRIMARY KEY,patient_id uuid NOT NULL,patient_identity_id uuid NOT NULL,doctor_id uuid,doctor_identity_id uuid,parent_id uuid REFERENCES appointments(id),start_at timestamptz NOT NULL,end_at timestamptz NOT NULL,status varchar(30) NOT NULL,reason varchar(500),cancel_reason varchar(500),idempotency_key varchar(100) UNIQUE,version bigint NOT NULL DEFAULT 0,created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now(),CHECK(start_at<end_at));
ALTER TABLE appointments ADD CONSTRAINT no_doctor_overlap EXCLUDE USING gist(doctor_id WITH =,tstzrange(start_at,end_at,'[)') WITH &&) WHERE(doctor_id IS NOT NULL AND status IN('ASSIGNED','CONFIRMED','IN_PROGRESS'));
CREATE INDEX ix_appointment_patient ON appointments(patient_id,start_at DESC);
CREATE INDEX ix_appointment_doctor ON appointments(doctor_id,start_at) WHERE status<>'CANCELLED';
CREATE TABLE outbox_events(id uuid PRIMARY KEY,aggregate_id uuid NOT NULL,event_type varchar(120) NOT NULL,payload jsonb NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),published_at timestamptz);
CREATE INDEX ix_outbox_pending ON outbox_events(created_at) WHERE published_at IS NULL;
