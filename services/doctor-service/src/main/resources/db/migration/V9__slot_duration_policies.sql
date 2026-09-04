CREATE TABLE slot_duration_policies(
 id uuid PRIMARY KEY,
 doctor_id uuid NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
 effective_from date NOT NULL,
 slot_minutes int NOT NULL CHECK(slot_minutes BETWEEN 10 AND 120),
 UNIQUE(doctor_id,effective_from)
);
CREATE INDEX ix_slot_duration_policy_doctor_date ON slot_duration_policies(doctor_id,effective_from DESC);
