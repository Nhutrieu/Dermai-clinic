-- The appointment keeps the agreed fee even when Admin changes the doctor's current price later.
ALTER TABLE appointments ADD COLUMN consultation_fee_snapshot numeric(12, 0);
UPDATE appointments SET consultation_fee_snapshot = 150000
WHERE doctor_id IS NOT NULL AND consultation_fee_snapshot IS NULL;
ALTER TABLE appointments ADD CONSTRAINT ck_appointment_consultation_fee_snapshot_non_negative
  CHECK (consultation_fee_snapshot IS NULL OR consultation_fee_snapshot >= 0);
ALTER TABLE appointments ADD CONSTRAINT ck_appointment_doctor_fee_pair
  CHECK (doctor_id IS NULL OR consultation_fee_snapshot IS NOT NULL);
