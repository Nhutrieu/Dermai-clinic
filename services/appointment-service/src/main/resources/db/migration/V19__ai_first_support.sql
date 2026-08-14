ALTER TABLE support_conversations
    ADD COLUMN channel_status varchar(30) NOT NULL DEFAULT 'WAITING_RECEPTIONIST',
    ADD COLUMN ai_failure_count integer NOT NULL DEFAULT 0,
    ADD COLUMN last_intent varchar(80),
    ADD COLUMN last_intent_confidence double precision,
    ADD COLUMN ai_summary varchar(4000),
    ADD COLUMN escalation_reason varchar(120),
    ADD COLUMN escalated_at timestamptz;

-- Existing conversations were created by the human-support flow and must stay
-- visible to receptionists after this migration.
UPDATE support_conversations
SET channel_status = CASE
    WHEN assigned_receptionist_identity_id IS NULL THEN 'WAITING_RECEPTIONIST'
    ELSE 'ASSIGNED'
END,
    escalated_at = COALESCE(assigned_at, updated_at),
    escalation_reason = 'LEGACY_HUMAN_CONVERSATION';

CREATE INDEX ix_support_conversations_status_updated
    ON support_conversations (channel_status, updated_at DESC);
