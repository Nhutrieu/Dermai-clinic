CREATE TABLE patients(id uuid PRIMARY KEY,identity_id uuid NOT NULL UNIQUE,full_name varchar(160) NOT NULL,dob date,phone varchar(30),medical_history text,allergies text,version bigint NOT NULL DEFAULT 0,created_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX ix_patient_name ON patients(lower(full_name));
