DO $$
BEGIN
  IF to_regclass('auth.identities') IS NOT NULL THEN
    UPDATE patient.patients AS patient
    SET account_linked = false
    WHERE NOT EXISTS (
      SELECT 1
      FROM auth.identities AS identity
      WHERE identity.id = patient.identity_id
    );
  END IF;
END $$;
