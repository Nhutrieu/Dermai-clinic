CREATE TABLE ai_assessments (
  id uuid PRIMARY KEY,
  patient_id uuid NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  patient_identity_id uuid NOT NULL,
  predicted_label varchar(80) NOT NULL,
  confidence double precision NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
  top3_json text NOT NULL,
  uncertain boolean NOT NULL DEFAULT false,
  model_version varchar(120) NOT NULL,
  shared_with_doctor boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ix_ai_assessments_patient_created
  ON ai_assessments(patient_identity_id, created_at DESC);
