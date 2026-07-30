ALTER TABLE identities ADD COLUMN email_verified_at timestamptz;

-- Existing demo/staff accounts remain usable; new password accounts must verify their email.
UPDATE identities SET email_verified_at = created_at WHERE email_verified_at IS NULL;

CREATE TABLE email_verification_otps(
 id uuid PRIMARY KEY,
 identity_id uuid NOT NULL REFERENCES identities(id) ON DELETE CASCADE,
 otp_hash text NOT NULL,
 created_at timestamptz NOT NULL,
 expires_at timestamptz NOT NULL,
 attempts int NOT NULL DEFAULT 0,
 used_at timestamptz
);
CREATE INDEX ix_email_verification_identity_created
 ON email_verification_otps(identity_id,created_at DESC);
