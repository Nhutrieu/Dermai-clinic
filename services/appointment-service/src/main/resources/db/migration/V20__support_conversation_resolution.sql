ALTER TABLE support_conversations
    ADD COLUMN resolved_at timestamptz,
    ADD COLUMN resolved_by_identity_id uuid;

-- Conversations that existed before AI-first support were already historical
-- human chats. Reopen them at the AI tier so they do not remain permanently in
-- the receptionist inbox after the migration. Their messages stay untouched.
INSERT INTO support_messages(
    id, patient_identity_id, sender_identity_id, sender_role, body, sent_at, read_at
)
SELECT
    gen_random_uuid(),
    patient_identity_id,
    patient_identity_id,
    'SYSTEM',
    'Yêu cầu hỗ trợ trước đây đã kết thúc. Yêu cầu mới sẽ được AI Assistant tiếp nhận trước.',
    now(),
    NULL
FROM support_conversations
WHERE escalation_reason = 'LEGACY_HUMAN_CONVERSATION';

UPDATE support_conversations
SET assigned_receptionist_identity_id = NULL,
    assigned_at = NULL,
    channel_status = 'AI_ACTIVE',
    ai_failure_count = 0,
    last_intent = NULL,
    last_intent_confidence = NULL,
    ai_summary = NULL,
    escalation_reason = NULL,
    escalated_at = NULL,
    resolved_at = now(),
    resolved_by_identity_id = NULL,
    updated_at = now()
WHERE escalation_reason = 'LEGACY_HUMAN_CONVERSATION';
