\set ON_ERROR_STOP on
BEGIN;
-- A prepaid appointment fixture for downstream integration checks after daily
-- booking slots have closed. This does not attest to the browser booking flow.
INSERT INTO appointment.appointments (
 id, patient_id, patient_identity_id, doctor_id, doctor_identity_id,
 start_at, end_at, status, reason, consultation_fee_snapshot
) VALUES (
 :'e2e_visit_id'::uuid,
 'e2e10000-0000-4000-8000-000000000002',
 'e2e00000-0000-4000-8000-000000000002',
 'e2e20000-0000-4000-8000-000000000001',
 'e2e00000-0000-4000-8000-000000000004',
 now(), now() + interval '30 minutes', 'PENDING_CONFIRMATION',
 'E2E-BILL-001 - prepaid same-day fixture', 150000
);
INSERT INTO payment.payments (
 id, booking_id, patient_identity_id, amount, order_code, status,
 appointment_start_at, expires_at
) VALUES (
 gen_random_uuid(), :'e2e_visit_id'::uuid,
 'e2e00000-0000-4000-8000-000000000002', 100000,
 nextval('payment.payment_order_code_seq'), 'SUCCESS', now(), now() + interval '10 minutes'
);
COMMIT;
