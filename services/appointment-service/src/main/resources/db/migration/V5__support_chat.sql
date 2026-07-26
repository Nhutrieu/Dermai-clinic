CREATE TABLE support_messages(id uuid PRIMARY KEY,patient_identity_id uuid NOT NULL,sender_identity_id uuid NOT NULL,sender_role varchar(30) NOT NULL,body varchar(2000) NOT NULL,sent_at timestamptz NOT NULL,read_at timestamptz);
CREATE INDEX ix_support_patient_time ON support_messages(patient_identity_id,sent_at);
