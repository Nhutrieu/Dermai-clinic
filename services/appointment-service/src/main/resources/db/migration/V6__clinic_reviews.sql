CREATE TABLE clinic_reviews(
 id uuid PRIMARY KEY,
 appointment_id uuid NOT NULL UNIQUE REFERENCES appointments(id),
 patient_identity_id uuid NOT NULL,
 display_name varchar(120) NOT NULL,
 rating smallint NOT NULL CHECK(rating BETWEEN 1 AND 5),
 comment varchar(1000) NOT NULL,
 status varchar(20) NOT NULL DEFAULT 'PENDING',
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_clinic_reviews_status ON clinic_reviews(status,created_at DESC);
