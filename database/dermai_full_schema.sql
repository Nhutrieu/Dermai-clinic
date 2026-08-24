-- DermAI Clinic - Full PostgreSQL schema
-- Generated from active microservice Flyway migrations only.
-- Target: a NEW/EMPTY PostgreSQL database (default Docker database: dermai).
-- Legacy clinic-service/public tables are intentionally excluded to avoid duplicate domain tables.
-- Do not run this file over an existing migrated database.

\set ON_ERROR_STOP on
BEGIN;
SET client_encoding = 'UTF8';
SET timezone = 'Asia/Ho_Chi_Minh';

-- ============================================================================
-- auth-service
-- ============================================================================
CREATE SCHEMA IF NOT EXISTS auth;
SET search_path TO auth, public;

-- Source: services/auth-service/src/main/resources/db/migration/V1__auth.sql
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

-- Source: services/auth-service/src/main/resources/db/migration/V2__refresh_token_hash_varchar.sql
ALTER TABLE refresh_tokens ALTER COLUMN token_hash TYPE varchar(64);

-- Source: services/auth-service/src/main/resources/db/migration/V3__google_identity.sql
ALTER TABLE identities
  ALTER COLUMN password_hash DROP NOT NULL,
  ADD COLUMN google_subject varchar(255);

CREATE UNIQUE INDEX ux_identities_google_subject
  ON identities(google_subject)
  WHERE google_subject IS NOT NULL;

-- Source: services/auth-service/src/main/resources/db/migration/V4__email_verification.sql
ALTER TABLE identities ADD COLUMN email_verified_at timestamptz;

-- Existing demo/staff accounts remain usable; new password accounts must verify their email.
UPDATE identities SET email_verified_at = created_at WHERE email_verified_at IS NULL;

CREATE TABLE email_verification_otps(
 id uuid PRIMARY KEY,
 identity_id uuid NOT NULL REFERENCES identities(id) ON DELETE CASCADE,
 otp_hash text NOT NULL,
 created_at timestamptz NOT NULL,
 expires_at timestamptz NOT NULL,
 attempts int NOT NULL DEFAULT 0,
 used_at timestamptz
);
CREATE INDEX ix_email_verification_identity_created
 ON email_verification_otps(identity_id,created_at DESC);

-- Source: services/auth-service/src/main/resources/db/migration/V5__staff_account_management.sql
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

-- Source: services/auth-service/src/main/resources/db/migration/V6__receptionist_avatar.sql
ALTER TABLE identities
    ADD COLUMN IF NOT EXISTS avatar_data BYTEA,
    ADD COLUMN IF NOT EXISTS avatar_mime VARCHAR(50);

-- ============================================================================
-- patient-service
-- ============================================================================
CREATE SCHEMA IF NOT EXISTS patient;
SET search_path TO patient, public;

-- Source: services/patient-service/src/main/resources/db/migration/V1__patient.sql
CREATE TABLE patients(id uuid PRIMARY KEY,identity_id uuid NOT NULL UNIQUE,full_name varchar(160) NOT NULL,dob date,phone varchar(30),medical_history text,allergies text,version bigint NOT NULL DEFAULT 0,created_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX ix_patient_name ON patients(lower(full_name));

-- Source: services/patient-service/src/main/resources/db/migration/V2__hotline_account_linking.sql
ALTER TABLE patients
  ADD COLUMN account_linked boolean NOT NULL DEFAULT true;

UPDATE patients
SET phone = regexp_replace(phone, '[^0-9+]', '', 'g')
WHERE phone IS NOT NULL;

CREATE UNIQUE INDEX uq_patients_phone
  ON patients(phone)
  WHERE phone IS NOT NULL AND phone <> '';

-- Source: services/patient-service/src/main/resources/db/migration/V3__detect_legacy_hotline_profiles.sql
DO $$
BEGIN
  IF to_regclass('auth.identities') IS NOT NULL THEN
    UPDATE patient.patients AS patient
    SET account_linked = false
    WHERE NOT EXISTS (
      SELECT 1
      FROM auth.identities AS identity
      WHERE identity.id = patient.identity_id
    );
  END IF;
END $$;

-- Source: services/patient-service/src/main/resources/db/migration/V4__canonicalize_patient_phones.sql
DROP INDEX IF EXISTS uq_patients_phone;

UPDATE patients
SET phone = NULLIF(
  CASE
    WHEN regexp_replace(COALESCE(phone, ''), '[^0-9]', '', 'g') LIKE '0084%'
      THEN '0' || substring(regexp_replace(phone, '[^0-9]', '', 'g') FROM 5)
    WHEN regexp_replace(COALESCE(phone, ''), '[^0-9]', '', 'g') LIKE '84%'
      THEN '0' || substring(regexp_replace(phone, '[^0-9]', '', 'g') FROM 3)
    ELSE regexp_replace(COALESCE(phone, ''), '[^0-9]', '', 'g')
  END,
  ''
);

ALTER TABLE patients
  ADD CONSTRAINT ck_patients_phone_vietnam
  CHECK (phone IS NULL OR phone ~ '^0[0-9]{8,10}$');

CREATE UNIQUE INDEX uq_patients_phone
  ON patients(phone)
  WHERE phone IS NOT NULL;

-- Source: services/patient-service/src/main/resources/db/migration/V5__patient_ai_assessments.sql
CREATE TABLE ai_assessments (
  id uuid PRIMARY KEY,
  patient_id uuid NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  patient_identity_id uuid NOT NULL,
  predicted_label varchar(80) NOT NULL,
  confidence double precision NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
  top3_json text NOT NULL,
  uncertain boolean NOT NULL DEFAULT false,
  model_version varchar(120) NOT NULL,
  shared_with_doctor boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ix_ai_assessments_patient_created
  ON ai_assessments(patient_identity_id, created_at DESC);

-- Source: services/patient-service/src/main/resources/db/migration/V6__share_ai_images_with_doctor.sql
ALTER TABLE ai_assessments
  ADD COLUMN appointment_id uuid,
  ADD COLUMN image_content_type varchar(80),
  ADD COLUMN image_bytes bytea;

CREATE UNIQUE INDEX ux_ai_assessments_shared_appointment
  ON ai_assessments(appointment_id)
  WHERE appointment_id IS NOT NULL AND shared_with_doctor = true;

-- ============================================================================
-- doctor-service
-- ============================================================================
CREATE SCHEMA IF NOT EXISTS doctor;
SET search_path TO doctor, public;

-- Source: services/doctor-service/src/main/resources/db/migration/V1__doctor.sql
CREATE TABLE doctors(id uuid PRIMARY KEY,identity_id uuid UNIQUE,full_name varchar(160) NOT NULL,specialty_code varchar(80) NOT NULL,experience_years int NOT NULL CHECK(experience_years>=0),certificate_no varchar(100),active boolean NOT NULL DEFAULT true);
CREATE INDEX ix_doctor_specialty ON doctors(specialty_code) WHERE active;
CREATE TABLE work_schedules(id uuid PRIMARY KEY,doctor_id uuid NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,weekday smallint NOT NULL CHECK(weekday BETWEEN 1 AND 7),start_time time NOT NULL,end_time time NOT NULL,slot_minutes int NOT NULL CHECK(slot_minutes BETWEEN 10 AND 120),CHECK(start_time<end_time),UNIQUE(doctor_id,weekday,start_time,end_time));
CREATE TABLE leave_periods(id uuid PRIMARY KEY,doctor_id uuid NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,start_at timestamptz NOT NULL,end_at timestamptz NOT NULL,reason varchar(250),CHECK(start_at<end_at));
CREATE INDEX ix_leave_doctor_time ON leave_periods(doctor_id,start_at,end_at);

-- Source: services/doctor-service/src/main/resources/db/migration/V2__doctor_avatar.sql
ALTER TABLE doctors ADD COLUMN avatar_url varchar(500);

-- Source: services/doctor-service/src/main/resources/db/migration/V3__doctor_avatar_binary.sql
ALTER TABLE doctors ADD COLUMN avatar_data bytea;
ALTER TABLE doctors ADD COLUMN avatar_mime varchar(50);

-- Source: services/doctor-service/src/main/resources/db/migration/V4__doctor_bio.sql
ALTER TABLE doctors ADD COLUMN bio varchar(1200);

-- Source: services/doctor-service/src/main/resources/db/migration/V5__doctor_consultation_fee.sql
-- Existing doctors start with the clinic's current base fee; Admin can adjust each profile afterward.
ALTER TABLE doctors ADD COLUMN consultation_fee numeric(12, 0);
UPDATE doctors SET consultation_fee = 150000 WHERE consultation_fee IS NULL;
ALTER TABLE doctors ALTER COLUMN consultation_fee SET NOT NULL;
ALTER TABLE doctors ADD CONSTRAINT ck_doctor_consultation_fee_non_negative CHECK (consultation_fee >= 0);

-- Source: services/doctor-service/src/main/resources/db/migration/V6__clinic_services.sql
CREATE TABLE clinic_services (
  id uuid PRIMARY KEY,
  code varchar(80) UNIQUE NOT NULL,
  name varchar(160) NOT NULL,
  description varchar(1000) NOT NULL,
  price_from numeric(12, 0) NOT NULL CHECK (price_from >= 0),
  duration_minutes int NOT NULL CHECK (duration_minutes BETWEEN 10 AND 240),
  display_order int NOT NULL DEFAULT 0,
  active boolean NOT NULL DEFAULT true
);

INSERT INTO clinic_services(id, code, name, description, price_from, duration_minutes, display_order) VALUES
('9c121521-0475-4a4c-a378-cd2a96ef31f1', 'DERM_EXAM', 'Khám da liễu chuyên sâu', 'Bác sĩ thăm khám, đánh giá tiền sử và xây dựng hướng chăm sóc phù hợp.', 150000, 30, 1),
('645559da-2625-44aa-8197-f8d35c11f2d2', 'ACNE', 'Điều trị mụn', 'Đánh giá tình trạng mụn, nguyên nhân và theo dõi đáp ứng theo từng giai đoạn.', 300000, 30, 2),
('664ca75a-9286-4ef9-b798-7bf20a15c18c', 'PIGMENT', 'Nám & sắc tố', 'Phân tích sắc tố và tư vấn liệu trình cá nhân hóa dưới sự theo dõi của bác sĩ.', 500000, 45, 3),
('a1fe780d-83e4-4bd7-b36a-77fd83b85ff9', 'REJUVENATION', 'Trẻ hóa làn da', 'Đánh giá cấu trúc da và tư vấn giải pháp cải thiện độ đàn hồi, bề mặt da.', 700000, 45, 4);

-- ============================================================================
-- appointment-service
-- ============================================================================
CREATE SCHEMA IF NOT EXISTS appointment;
SET search_path TO appointment, public;

-- Source: services/appointment-service/src/main/resources/db/migration/V1__appointment.sql
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE TABLE appointments(id uuid PRIMARY KEY,patient_id uuid NOT NULL,patient_identity_id uuid NOT NULL,doctor_id uuid,doctor_identity_id uuid,parent_id uuid REFERENCES appointments(id),start_at timestamptz NOT NULL,end_at timestamptz NOT NULL,status varchar(30) NOT NULL,reason varchar(500),cancel_reason varchar(500),idempotency_key varchar(100) UNIQUE,version bigint NOT NULL DEFAULT 0,created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now(),CHECK(start_at<end_at));
ALTER TABLE appointments ADD CONSTRAINT no_doctor_overlap EXCLUDE USING gist(doctor_id WITH =,tstzrange(start_at,end_at,'[)') WITH &&) WHERE(doctor_id IS NOT NULL AND status IN('ASSIGNED','CONFIRMED','IN_PROGRESS'));
CREATE INDEX ix_appointment_patient ON appointments(patient_id,start_at DESC);
CREATE INDEX ix_appointment_doctor ON appointments(doctor_id,start_at) WHERE status<>'CANCELLED';
CREATE TABLE outbox_events(id uuid PRIMARY KEY,aggregate_id uuid NOT NULL,event_type varchar(120) NOT NULL,payload jsonb NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),published_at timestamptz);
CREATE INDEX ix_outbox_pending ON outbox_events(created_at) WHERE published_at IS NULL;

-- Source: services/appointment-service/src/main/resources/db/migration/V2__identity_ownership.sql
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS patient_identity_id uuid;
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS doctor_identity_id uuid;
CREATE INDEX IF NOT EXISTS ix_appointment_patient_identity ON appointments(patient_identity_id,start_at DESC);
CREATE INDEX IF NOT EXISTS ix_appointment_doctor_identity ON appointments(doctor_identity_id,start_at) WHERE status<>'CANCELLED';

-- Không tự suy diễn identity cho dữ liệu cũ. Các bản ghi legacy thiếu identity
-- phải được đối soát bằng Auth/Patient/Doctor service trước khi gán thủ công.

-- Source: services/appointment-service/src/main/resources/db/migration/V3__one_active_appointment_per_patient.sql
create unique index if not exists uq_patient_active_appointment
    on appointment.appointments(patient_identity_id)
    where status in ('PENDING','ASSIGNED','CONFIRMED','IN_PROGRESS');

-- Source: services/appointment-service/src/main/resources/db/migration/V4__follow_up_reason.sql
alter table appointment.appointments
    add column if not exists follow_up_reason varchar(500),
    add column if not exists follow_up_not_before timestamptz;

-- Source: services/appointment-service/src/main/resources/db/migration/V5__support_chat.sql
CREATE TABLE support_messages(id uuid PRIMARY KEY,patient_identity_id uuid NOT NULL,sender_identity_id uuid NOT NULL,sender_role varchar(30) NOT NULL,body varchar(2000) NOT NULL,sent_at timestamptz NOT NULL,read_at timestamptz);
CREATE INDEX ix_support_patient_time ON support_messages(patient_identity_id,sent_at);

-- Source: services/appointment-service/src/main/resources/db/migration/V6__clinic_reviews.sql
CREATE TABLE clinic_reviews(
 id uuid PRIMARY KEY,
 appointment_id uuid NOT NULL UNIQUE REFERENCES appointments(id),
 patient_identity_id uuid NOT NULL,
 display_name varchar(120) NOT NULL,
 rating smallint NOT NULL CHECK(rating BETWEEN 1 AND 5),
 comment varchar(1000) NOT NULL,
 status varchar(20) NOT NULL DEFAULT 'PENDING',
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_clinic_reviews_status ON clinic_reviews(status,created_at DESC);

-- Source: services/appointment-service/src/main/resources/db/migration/V7__patient_hide_cancelled_appointments.sql
ALTER TABLE appointments ADD COLUMN patient_hidden boolean NOT NULL DEFAULT false;

-- Source: services/appointment-service/src/main/resources/db/migration/V8__booking_safety_and_notifications.sql
ALTER TABLE appointments ADD COLUMN hold_expires_at timestamptz;

DROP INDEX IF EXISTS uq_patient_active_appointment;
ALTER TABLE appointments DROP CONSTRAINT IF EXISTS no_doctor_overlap;

ALTER TABLE appointments ADD CONSTRAINT no_doctor_overlap
  EXCLUDE USING gist (
    doctor_id WITH =,
    tstzrange(start_at, end_at, '[)') WITH &&
  )
  WHERE (doctor_id IS NOT NULL AND status IN ('HELD','PENDING','ASSIGNED','CONFIRMED','IN_PROGRESS'));

ALTER TABLE appointments ADD CONSTRAINT no_patient_overlap
  EXCLUDE USING gist (
    patient_identity_id WITH =,
    tstzrange(start_at, end_at, '[)') WITH &&
  )
  WHERE (status IN ('HELD','PENDING','ASSIGNED','CONFIRMED','IN_PROGRESS'));

CREATE INDEX ix_expiring_holds ON appointments(hold_expires_at)
  WHERE status = 'HELD';

CREATE TABLE clinic_closures (
  id uuid PRIMARY KEY,
  closure_date date NOT NULL UNIQUE,
  reason varchar(300) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE appointment_notifications (
  id uuid PRIMARY KEY,
  patient_identity_id uuid NOT NULL,
  appointment_id uuid REFERENCES appointments(id) ON DELETE CASCADE,
  notification_type varchar(50) NOT NULL,
  title varchar(160) NOT NULL,
  body varchar(500) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  read_at timestamptz,
  UNIQUE (appointment_id, notification_type)
);

CREATE INDEX ix_notification_patient ON appointment_notifications(patient_identity_id, created_at DESC);

-- Source: services/appointment-service/src/main/resources/db/migration/V9__reception_reminder_actions.sql
CREATE TABLE reminder_actions (
  id uuid PRIMARY KEY,
  appointment_id uuid NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
  receptionist_identity_id uuid NOT NULL,
  action_type varchar(30) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ix_reminder_action_appointment
  ON reminder_actions(appointment_id, created_at DESC);

-- Source: services/appointment-service/src/main/resources/db/migration/V10__expand_manual_notification_type.sql
ALTER TABLE appointment_notifications
  ALTER COLUMN notification_type TYPE varchar(100);

INSERT INTO appointment_notifications(
  id, patient_identity_id, appointment_id, notification_type,
  title, body, created_at
)
SELECT
  ra.id,
  a.patient_identity_id,
  a.id,
  'MANUAL_REMINDER_' || ra.id,
  'Nhắc lịch khám từ lễ tân',
  'Bạn có lịch khám sắp tới. Vui lòng kiểm tra thời gian và đến đúng giờ.',
  ra.created_at
FROM reminder_actions ra
JOIN appointments a ON a.id = ra.appointment_id
WHERE ra.action_type = 'RESENT'
  AND NOT EXISTS (
    SELECT 1 FROM appointment_notifications n WHERE n.id = ra.id
  );

-- Source: services/appointment-service/src/main/resources/db/migration/V11__deduplicate_manual_reminders.sql
DELETE FROM appointment_notifications n
USING (
  SELECT id, row_number() OVER (
    PARTITION BY appointment_id
    ORDER BY created_at DESC, id DESC
  ) AS position
  FROM appointment_notifications
  WHERE notification_type LIKE 'MANUAL_REMINDER_%'
) duplicates
WHERE n.id = duplicates.id
  AND duplicates.position > 1;

-- Source: services/appointment-service/src/main/resources/db/migration/V12__reception_booking_proposals.sql
ALTER TABLE appointments DROP CONSTRAINT IF EXISTS no_doctor_overlap;
ALTER TABLE appointments DROP CONSTRAINT IF EXISTS no_patient_overlap;

ALTER TABLE appointments ADD CONSTRAINT no_doctor_overlap
  EXCLUDE USING gist (
    doctor_id WITH =,
    tstzrange(start_at, end_at, '[)') WITH &&
  )
  WHERE (doctor_id IS NOT NULL AND status IN ('HELD','PROPOSED','PENDING','ASSIGNED','CONFIRMED','IN_PROGRESS'));

ALTER TABLE appointments ADD CONSTRAINT no_patient_overlap
  EXCLUDE USING gist (
    patient_identity_id WITH =,
    tstzrange(start_at, end_at, '[)') WITH &&
  )
  WHERE (status IN ('HELD','PROPOSED','PENDING','ASSIGNED','CONFIRMED','IN_PROGRESS'));

CREATE INDEX IF NOT EXISTS ix_expiring_proposals ON appointments(hold_expires_at)
  WHERE status = 'PROPOSED';

-- Source: services/appointment-service/src/main/resources/db/migration/V13__repair_confirmed_no_show_status.sql
-- Older maintenance logic labelled every unstarted appointment as CANCELLED.
-- Repair only rows with persisted confirmation evidence so unconfirmed requests
-- are not incorrectly presented as patient no-shows.
UPDATE appointments AS appointment
SET status = 'NO_SHOW',
    cancel_reason = NULL,
    updated_at = CURRENT_TIMESTAMP
WHERE appointment.status = 'CANCELLED'
  AND appointment.cancel_reason LIKE 'Tự động hủy:%'
  AND EXISTS (
    SELECT 1
    FROM outbox_events AS event
    WHERE event.aggregate_id = appointment.id
      AND event.event_type IN ('AppointmentCONFIRMED', 'AppointmentConfirmedByPatient')
  );

-- Source: services/appointment-service/src/main/resources/db/migration/V14__backfill_no_show_notifications.sql
-- Ensure historical NO_SHOW appointments also produce an unread patient warning.
INSERT INTO appointment_notifications (
  id,
  patient_identity_id,
  appointment_id,
  notification_type,
  title,
  body,
  created_at,
  read_at
)
SELECT
  gen_random_uuid(),
  appointment.patient_identity_id,
  appointment.id,
  'NO_SHOW',
  'Cảnh báo: Bạn đã bỏ lỡ lịch khám',
  'Hệ thống ghi nhận bạn chưa đến theo lịch đã xác nhận. Nếu có nhầm lẫn hoặc cần đặt lại lịch, vui lòng liên hệ lễ tân qua chat hỗ trợ hoặc hotline 0352 790 904.',
  COALESCE(appointment.updated_at, CURRENT_TIMESTAMP),
  NULL
FROM appointments AS appointment
WHERE appointment.status = 'NO_SHOW'
  AND NOT EXISTS (
    SELECT 1
    FROM appointment_notifications AS notification
    WHERE notification.appointment_id = appointment.id
      AND notification.notification_type = 'NO_SHOW'
  );

-- Source: services/appointment-service/src/main/resources/db/migration/V15__appointment_consultation_fee_snapshot.sql
-- The appointment keeps the agreed fee even when Admin changes the doctor's current price later.
ALTER TABLE appointments ADD COLUMN consultation_fee_snapshot numeric(12, 0);
UPDATE appointments SET consultation_fee_snapshot = 150000
WHERE doctor_id IS NOT NULL AND consultation_fee_snapshot IS NULL;
ALTER TABLE appointments ADD CONSTRAINT ck_appointment_consultation_fee_snapshot_non_negative
  CHECK (consultation_fee_snapshot IS NULL OR consultation_fee_snapshot >= 0);
ALTER TABLE appointments ADD CONSTRAINT ck_appointment_doctor_fee_pair
  CHECK (doctor_id IS NULL OR consultation_fee_snapshot IS NOT NULL);

-- Source: services/appointment-service/src/main/resources/db/migration/V16__appointment_check_in.sql
ALTER TABLE appointments
    ADD COLUMN IF NOT EXISTS checked_in_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_appointments_checked_in_at
    ON appointments (checked_in_at)
    WHERE checked_in_at IS NOT NULL;

-- An arrived patient still occupies the reserved slot. Keep CHECKED_IN inside
-- both exclusion constraints so another booking cannot overlap it.
ALTER TABLE appointments DROP CONSTRAINT IF EXISTS no_doctor_overlap;
ALTER TABLE appointments ADD CONSTRAINT no_doctor_overlap
    EXCLUDE USING gist (
        doctor_id WITH =,
        tstzrange(start_at, end_at, '[)') WITH &&
    )
    WHERE (doctor_id IS NOT NULL AND status IN ('HELD','PROPOSED','PENDING','ASSIGNED','CONFIRMED','CHECKED_IN','IN_PROGRESS'));

ALTER TABLE appointments DROP CONSTRAINT IF EXISTS no_patient_overlap;
ALTER TABLE appointments ADD CONSTRAINT no_patient_overlap
    EXCLUDE USING gist (
        patient_identity_id WITH =,
        tstzrange(start_at, end_at, '[)') WITH &&
    )
    WHERE (status IN ('HELD','PROPOSED','PENDING','ASSIGNED','CONFIRMED','CHECKED_IN','IN_PROGRESS'));

-- Source: services/appointment-service/src/main/resources/db/migration/V17__appointment_staff_action_audit.sql
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

-- Source: services/appointment-service/src/main/resources/db/migration/V18__support_conversation_assignment.sql
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

-- Source: services/appointment-service/src/main/resources/db/migration/V19__ai_first_support.sql
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

-- Source: services/appointment-service/src/main/resources/db/migration/V20__support_conversation_resolution.sql
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

-- Source: services/appointment-service/src/main/resources/db/migration/V21__close_stranded_pre_ai_support.sql
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

-- Source: services/appointment-service/src/main/resources/db/migration/V22__rename_ai_assistant_in_support_history.sql
-- Keep existing support history, but use the patient-facing DermAI name
-- consistently for system messages created before this terminology change.
UPDATE support_messages
SET body = REPLACE(body, 'AI Assistant', 'Trợ lý DermAI')
WHERE body LIKE '%AI Assistant%';

-- ============================================================================
-- medical-record-service
-- ============================================================================
CREATE SCHEMA IF NOT EXISTS medical_record;
SET search_path TO medical_record, public;

-- Source: services/medical-record-service/src/main/resources/db/migration/V1__record.sql
CREATE TABLE medical_records(id uuid PRIMARY KEY,appointment_id uuid NOT NULL UNIQUE,patient_id uuid NOT NULL,patient_identity_id uuid NOT NULL,doctor_id uuid NOT NULL,final_diagnosis varchar(2000) NOT NULL,clinical_notes varchar(10000),treatment_plan varchar(5000),severity varchar(20) NOT NULL,follow_up_at timestamptz,signed_at timestamptz NOT NULL,version bigint NOT NULL DEFAULT 0);
CREATE INDEX ix_record_patient ON medical_records(patient_id,signed_at DESC);

-- Source: services/medical-record-service/src/main/resources/db/migration/V2__patient_identity.sql
ALTER TABLE medical_records ADD COLUMN IF NOT EXISTS patient_identity_id uuid;
CREATE INDEX IF NOT EXISTS ix_record_patient_identity ON medical_records(patient_identity_id,signed_at DESC);

-- Source: services/medical-record-service/src/main/resources/db/migration/V3__patient_record_visibility.sql
CREATE TABLE IF NOT EXISTS patient_record_visibility (
    record_id uuid PRIMARY KEY REFERENCES medical_records(id),
    patient_identity_id uuid NOT NULL,
    hidden_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_patient_record_visibility_patient
    ON patient_record_visibility(patient_identity_id, hidden_at DESC);

-- ============================================================================
-- prescription-service
-- ============================================================================
CREATE SCHEMA IF NOT EXISTS prescription;
SET search_path TO prescription, public;

-- Source: services/prescription-service/src/main/resources/db/migration/V1__prescription.sql
CREATE TABLE prescriptions(id uuid PRIMARY KEY,record_id uuid NOT NULL,patient_id uuid NOT NULL,patient_identity_id uuid NOT NULL,doctor_id uuid NOT NULL,instructions varchar(3000),signed_at timestamptz NOT NULL);
CREATE TABLE prescription_items(prescription_id uuid NOT NULL REFERENCES prescriptions(id) ON DELETE CASCADE,drug_name varchar(200) NOT NULL,dosage varchar(120) NOT NULL,frequency varchar(120),duration varchar(120),item_instructions varchar(1000));
CREATE INDEX ix_prescription_patient ON prescriptions(patient_id,signed_at DESC);

-- Source: services/prescription-service/src/main/resources/db/migration/V2__patient_identity.sql
ALTER TABLE prescriptions ADD COLUMN IF NOT EXISTS patient_identity_id uuid;
CREATE INDEX IF NOT EXISTS ix_prescription_patient_identity ON prescriptions(patient_identity_id,signed_at DESC);

-- Source: services/prescription-service/src/main/resources/db/migration/V3__one_prescription_per_record.sql
create unique index if not exists uq_prescription_record
    on prescription.prescriptions(record_id);

-- ============================================================================
-- notification-service
-- ============================================================================
CREATE SCHEMA IF NOT EXISTS notification;
SET search_path TO notification, public;

-- Source: services/notification-service/src/main/resources/db/migration/V1__notification.sql
CREATE TABLE deliveries(id uuid PRIMARY KEY,event_id uuid NOT NULL UNIQUE,event_type varchar(120) NOT NULL,recipient varchar(320) NOT NULL,subject varchar(300) NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),sent_at timestamptz,last_error varchar(2000),attempts int NOT NULL DEFAULT 0);
CREATE INDEX ix_delivery_unsent ON deliveries(created_at) WHERE sent_at IS NULL;

SET search_path TO public;
COMMIT;
