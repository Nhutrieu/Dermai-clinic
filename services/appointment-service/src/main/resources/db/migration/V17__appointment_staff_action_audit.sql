CREATE TABLE appointment_action_logs (
    id UUID PRIMARY KEY,
    appointment_id UUID NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
    actor_identity_id UUID NOT NULL,
    actor_role VARCHAR(20) NOT NULL,
    action_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_appointment_action_actor_created
    ON appointment_action_logs (actor_identity_id, created_at DESC);

CREATE INDEX ix_appointment_action_appointment_created
    ON appointment_action_logs (appointment_id, created_at DESC);
