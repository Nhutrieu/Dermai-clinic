DROP INDEX IF EXISTS uq_patients_phone;

UPDATE patients
SET phone = NULLIF(
  CASE
    WHEN regexp_replace(COALESCE(phone, ''), '[^0-9]', '', 'g') LIKE '0084%'
      THEN '0' || substring(regexp_replace(phone, '[^0-9]', '', 'g') FROM 5)
    WHEN regexp_replace(COALESCE(phone, ''), '[^0-9]', '', 'g') LIKE '84%'
      THEN '0' || substring(regexp_replace(phone, '[^0-9]', '', 'g') FROM 3)
    ELSE regexp_replace(COALESCE(phone, ''), '[^0-9]', '', 'g')
  END,
  ''
);

ALTER TABLE patients
  ADD CONSTRAINT ck_patients_phone_vietnam
  CHECK (phone IS NULL OR phone ~ '^0[0-9]{8,10}$');

CREATE UNIQUE INDEX uq_patients_phone
  ON patients(phone)
  WHERE phone IS NOT NULL;
