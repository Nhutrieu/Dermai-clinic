CREATE TABLE identities(
 id uuid PRIMARY KEY,email varchar(320) NOT NULL UNIQUE,password_hash text NOT NULL,
 role varchar(20) NOT NULL,status varchar(20) NOT NULL,created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE refresh_tokens(
 id uuid PRIMARY KEY,identity_id uuid NOT NULL REFERENCES identities(id) ON DELETE CASCADE,
 token_hash char(64) NOT NULL UNIQUE,expires_at timestamptz NOT NULL,revoked_at timestamptz
);
CREATE INDEX ix_refresh_identity ON refresh_tokens(identity_id);
CREATE TABLE password_otps(
 id uuid PRIMARY KEY,identity_id uuid NOT NULL REFERENCES identities(id) ON DELETE CASCADE,
 otp_hash text NOT NULL,expires_at timestamptz NOT NULL,attempts int NOT NULL DEFAULT 0,used_at timestamptz
);
CREATE INDEX ix_otp_identity_expiry ON password_otps(identity_id,expires_at DESC);
