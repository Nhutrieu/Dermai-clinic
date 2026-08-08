-- Existing doctors start with the clinic's current base fee; Admin can adjust each profile afterward.
ALTER TABLE doctors ADD COLUMN consultation_fee numeric(12, 0);
UPDATE doctors SET consultation_fee = 150000 WHERE consultation_fee IS NULL;
ALTER TABLE doctors ALTER COLUMN consultation_fee SET NOT NULL;
ALTER TABLE doctors ADD CONSTRAINT ck_doctor_consultation_fee_non_negative CHECK (consultation_fee >= 0);
