ALTER TABLE identities
    ADD COLUMN IF NOT EXISTS display_name VARCHAR(150);

CREATE TABLE staff_account_events (
    id UUID PRIMARY KEY,
    staff_identity_id UUID NOT NULL REFERENCES identities(id),
    actor_identity_id UUID NOT NULL REFERENCES identities(id),
    action_type VARCHAR(40) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_staff_account_events_staff_created
    ON staff_account_events (staff_identity_id, created_at DESC);
