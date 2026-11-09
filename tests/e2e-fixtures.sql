\set ON_ERROR_STOP on
BEGIN;
SELECT 1 / CASE WHEN count(*) = 0 THEN 1 ELSE 0 END AS fresh_database_required FROM auth.identities;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Dedicated synthetic identities. Run only against the isolated E2E database.
INSERT INTO auth.identities (id, email, password_hash, role, status, email_verified_at, display_name)
SELECT id::uuid, email, crypt(:'e2e_password', gen_salt('bf', 12)), role, 'ACTIVE', now(), name
FROM (VALUES
 ('e2e00000-0000-4000-8000-000000000001', 'patient-1@e2e.example.test', 'PATIENT', 'E2E Patient One'),
 ('e2e00000-0000-4000-8000-000000000002', 'patient-2@e2e.example.test', 'PATIENT', 'E2E Patient Two'),
 ('e2e00000-0000-4000-8000-000000000003', 'reception@e2e.example.test', 'RECEPTIONIST', 'E2E Reception'),
 ('e2e00000-0000-4000-8000-000000000004', 'doctor@e2e.example.test', 'DOCTOR', 'E2E Doctor'),
 ('e2e00000-0000-4000-8000-000000000005', 'pharmacist@e2e.example.test', 'PHARMACIST', 'E2E Pharmacist'),
 ('e2e00000-0000-4000-8000-000000000006', 'admin@e2e.example.test', 'ADMIN', 'E2E Admin')
) AS fixture(id, email, role, name);

INSERT INTO patient.patients (id, identity_id, full_name, dob, phone)
VALUES
 ('e2e10000-0000-4000-8000-000000000001', 'e2e00000-0000-4000-8000-000000000001', 'E2E Patient One', '2000-01-01', '0900000001'),
 ('e2e10000-0000-4000-8000-000000000002', 'e2e00000-0000-4000-8000-000000000002', 'E2E Patient Two', '2000-01-02', '0900000002');

INSERT INTO doctor.doctors (id, identity_id, full_name, specialty_code, experience_years, certificate_no, consultation_fee, active)
SELECT 'e2e20000-0000-4000-8000-000000000001', 'e2e00000-0000-4000-8000-000000000004', 'E2E Doctor', specialty_code, 5, 'E2E-ONLY', 150000, true
FROM doctor.clinic_services WHERE code = 'DERM_EXAM';

-- Daily fixture schedule keeps the same-day check-in scenario runnable at night.
INSERT INTO doctor.work_schedules (id, doctor_id, weekday, start_time, end_time, slot_minutes)
SELECT gen_random_uuid(), 'e2e20000-0000-4000-8000-000000000001', day, '00:29', '23:59', 30
FROM generate_series(1, 7) AS day;

INSERT INTO doctor.clinic_service_doctors (service_id, doctor_id)
SELECT id, 'e2e20000-0000-4000-8000-000000000001'
FROM doctor.clinic_services WHERE code = 'DERM_EXAM';
COMMIT;
