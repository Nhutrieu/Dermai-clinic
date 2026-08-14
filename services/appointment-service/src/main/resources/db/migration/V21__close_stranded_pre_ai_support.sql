-- A patient could submit a direct receptionist message while the old frontend
-- was still open during the AI-first deployment. If that thread has never had
-- an AI turn and nobody claimed it, return it to AI instead of leaving a stale
-- receptionist banner forever. All historical messages remain available.
INSERT INTO support_messages(
    id, patient_identity_id, sender_identity_id, sender_role, body, sent_at, read_at
)
SELECT
    gen_random_uuid(),
    conversation.patient_identity_id,
    conversation.patient_identity_id,
    'SYSTEM',
    'Yêu cầu hỗ trợ cũ đã được đóng. Bạn có thể gửi yêu cầu mới để AI Assistant hỗ trợ trước.',
    now(),
    NULL
FROM support_conversations conversation
WHERE conversation.channel_status = 'WAITING_RECEPTIONIST'
  AND conversation.assigned_receptionist_identity_id IS NULL
  AND conversation.escalation_reason = 'PATIENT_DIRECT_MESSAGE'
  AND NOT EXISTS (
      SELECT 1
      FROM support_messages message
      WHERE message.patient_identity_id = conversation.patient_identity_id
        AND message.sender_role = 'AI'
  );

UPDATE support_conversations conversation
SET channel_status = 'AI_ACTIVE',
    ai_failure_count = 0,
    last_intent = NULL,
    last_intent_confidence = NULL,
    ai_summary = NULL,
    escalation_reason = NULL,
    escalated_at = NULL,
    resolved_at = now(),
    resolved_by_identity_id = NULL,
    updated_at = now()
WHERE conversation.channel_status = 'WAITING_RECEPTIONIST'
  AND conversation.assigned_receptionist_identity_id IS NULL
  AND conversation.escalation_reason = 'PATIENT_DIRECT_MESSAGE'
  AND NOT EXISTS (
      SELECT 1
      FROM support_messages message
      WHERE message.patient_identity_id = conversation.patient_identity_id
        AND message.sender_role = 'AI'
  );
