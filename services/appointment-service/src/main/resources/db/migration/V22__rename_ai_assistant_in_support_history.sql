-- Keep existing support history, but use the patient-facing DermAI name
-- consistently for system messages created before this terminology change.
UPDATE support_messages
SET body = REPLACE(body, 'AI Assistant', 'Trợ lý DermAI')
WHERE body LIKE '%AI Assistant%';
