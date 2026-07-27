ALTER TABLE patients
  ADD COLUMN account_linked boolean NOT NULL DEFAULT true;

UPDATE patients
SET phone = regexp_replace(phone, '[^0-9+]', '', 'g')
WHERE phone IS NOT NULL;

CREATE UNIQUE INDEX uq_patients_phone
  ON patients(phone)
  WHERE phone IS NOT NULL AND phone <> '';
