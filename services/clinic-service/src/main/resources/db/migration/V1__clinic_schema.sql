CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE TABLE users (
 id uuid PRIMARY KEY, email citext NOT NULL UNIQUE, password_hash text NOT NULL,
 role varchar(20) NOT NULL CHECK(role IN ('ADMIN','RECEPTIONIST','DOCTOR','PATIENT')),
 status varchar(20) NOT NULL DEFAULT 'ACTIVE', created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE specialties (id uuid PRIMARY KEY, code varchar(50) UNIQUE NOT NULL, name varchar(120) NOT NULL);
CREATE TABLE patients (
 id uuid PRIMARY KEY, user_id uuid UNIQUE REFERENCES users(id), full_name varchar(160) NOT NULL,
 dob date, phone varchar(30), medical_history text, allergies text, version bigint NOT NULL DEFAULT 0
);
CREATE TABLE doctors (
 id uuid PRIMARY KEY, user_id uuid UNIQUE REFERENCES users(id), specialty_id uuid REFERENCES specialties(id),
 full_name varchar(160) NOT NULL, experience_years int CHECK(experience_years >= 0),
 certificate_no varchar(100), active boolean NOT NULL DEFAULT true
);
CREATE TABLE work_schedules (
 id uuid PRIMARY KEY, doctor_id uuid NOT NULL REFERENCES doctors(id), weekday smallint NOT NULL CHECK(weekday BETWEEN 1 AND 7),
 start_time time NOT NULL, end_time time NOT NULL, slot_minutes int NOT NULL DEFAULT 30,
 CHECK(start_time < end_time), UNIQUE(doctor_id,weekday,start_time,end_time)
);
CREATE TABLE leave_periods (
 id uuid PRIMARY KEY, doctor_id uuid NOT NULL REFERENCES doctors(id), start_at timestamptz NOT NULL,
 end_at timestamptz NOT NULL, reason varchar(250), CHECK(start_at < end_at)
);
CREATE TABLE appointments (
 id uuid PRIMARY KEY, patient_id uuid NOT NULL REFERENCES patients(id), doctor_id uuid REFERENCES doctors(id),
 parent_id uuid REFERENCES appointments(id), start_at timestamptz NOT NULL, end_at timestamptz NOT NULL,
 status varchar(30) NOT NULL, reason varchar(500), cancel_reason varchar(500),
 idempotency_key varchar(100) UNIQUE, version bigint NOT NULL DEFAULT 0,
 created_at timestamptz NOT NULL DEFAULT now(), CHECK(start_at < end_at)
);
ALTER TABLE appointments ADD CONSTRAINT no_doctor_overlap EXCLUDE USING gist
 (doctor_id WITH =, tstzrange(start_at,end_at,'[)') WITH &&)
 WHERE (doctor_id IS NOT NULL AND status IN ('ASSIGNED','CONFIRMED','IN_PROGRESS'));
CREATE INDEX ix_appointments_patient_time ON appointments(patient_id,start_at DESC);
CREATE INDEX ix_appointments_doctor_time ON appointments(doctor_id,start_at) WHERE status <> 'CANCELLED';
CREATE TABLE medical_records (
 id uuid PRIMARY KEY, appointment_id uuid NOT NULL UNIQUE REFERENCES appointments(id),
 final_diagnosis text NOT NULL, clinical_notes text, treatment_plan text,
 severity varchar(20), follow_up_at timestamptz, signed_by uuid NOT NULL REFERENCES doctors(id),
 signed_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE prescriptions (
 id uuid PRIMARY KEY, record_id uuid NOT NULL REFERENCES medical_records(id),
 doctor_id uuid NOT NULL REFERENCES doctors(id), instructions text, signed_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE prescription_items (
 id uuid PRIMARY KEY, prescription_id uuid NOT NULL REFERENCES prescriptions(id) ON DELETE CASCADE,
 drug_name varchar(200) NOT NULL, dosage varchar(120) NOT NULL,
 frequency varchar(120), duration varchar(120), instructions text
);
CREATE TABLE outbox_events (
 id uuid PRIMARY KEY, aggregate_type varchar(80) NOT NULL, aggregate_id uuid NOT NULL,
 event_type varchar(120) NOT NULL, payload jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 published_at timestamptz
);
CREATE INDEX ix_outbox_unpublished ON outbox_events(created_at) WHERE published_at IS NULL;
CREATE TABLE audit_logs (
 id bigserial PRIMARY KEY, actor_id uuid, action varchar(100) NOT NULL, resource_type varchar(80) NOT NULL,
 resource_id varchar(100), trace_id varchar(100), metadata jsonb NOT NULL DEFAULT '{}',
 created_at timestamptz NOT NULL DEFAULT now()
);
