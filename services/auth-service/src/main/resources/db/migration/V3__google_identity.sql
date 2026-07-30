ALTER TABLE identities
  ALTER COLUMN password_hash DROP NOT NULL,
  ADD COLUMN google_subject varchar(255);

CREATE UNIQUE INDEX ux_identities_google_subject
  ON identities(google_subject)
  WHERE google_subject IS NOT NULL;
