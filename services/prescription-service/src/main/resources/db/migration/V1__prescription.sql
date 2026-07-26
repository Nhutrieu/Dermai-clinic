CREATE TABLE prescriptions(id uuid PRIMARY KEY,record_id uuid NOT NULL,patient_id uuid NOT NULL,patient_identity_id uuid NOT NULL,doctor_id uuid NOT NULL,instructions varchar(3000),signed_at timestamptz NOT NULL);
CREATE TABLE prescription_items(prescription_id uuid NOT NULL REFERENCES prescriptions(id) ON DELETE CASCADE,drug_name varchar(200) NOT NULL,dosage varchar(120) NOT NULL,frequency varchar(120),duration varchar(120),item_instructions varchar(1000));
CREATE INDEX ix_prescription_patient ON prescriptions(patient_id,signed_at DESC);
