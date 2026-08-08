CREATE TABLE support_conversations (
    patient_identity_id UUID PRIMARY KEY,
    assigned_receptionist_identity_id UUID,
    assigned_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO support_conversations(patient_identity_id, updated_at)
SELECT patient_identity_id, MAX(sent_at)
FROM support_messages
GROUP BY patient_identity_id
ON CONFLICT (patient_identity_id) DO NOTHING;

CREATE INDEX ix_support_conversations_assignee_updated
    ON support_conversations (assigned_receptionist_identity_id, updated_at DESC);
