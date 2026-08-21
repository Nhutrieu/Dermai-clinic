# DermAI Clinic — tham chiếu database cho ERD và class diagram

Tài liệu này được đối chiếu với PostgreSQL đang chạy và các Flyway migration ngày
21/08/2026. Nguồn vẽ đầy đủ nằm tại:

- `docs/diagrams/database-erd.puml`: ERD đủ 24 bảng và 196 cột.
- `docs/diagrams/database-class.puml`: class diagram của các entity/value object.

Không đưa bảy bảng `flyway_schema_history` vào ERD nghiệp vụ. Chúng chỉ lưu lịch sử
migration của từng schema.

## 1. Quy ước

- `PK`: khóa chính.
- `FK`: khóa ngoại vật lý được PostgreSQL thực thi.
- `UQ`: unique constraint hoặc unique index.
- `NN`: `NOT NULL`.
- `REF`: tham chiếu logic bằng UUID qua API giữa hai microservice; database không tạo
  foreign key chéo service.
- Thuộc tính không có `NN` là nullable.

## 2. Tổng số bảng

| Schema | Service sở hữu | Bảng nghiệp vụ |
|---|---|---:|
| `auth` | Auth service | 5 |
| `patient` | Patient service | 2 |
| `doctor` | Doctor service | 3 |
| `appointment` | Appointment service | 9 |
| `medical_record` | Medical record service | 2 |
| `prescription` | Prescription service | 2 |
| `notification` | Notification service | 1 |
| **Tổng** | **7 service dữ liệu** | **24** |

## 3. Thuộc tính của 24 bảng

### 3.1. Auth schema

1. `auth.identities`
   - `id uuid PK NN`
   - `email varchar NN UQ`
   - `password_hash text`
   - `role varchar NN`
   - `status varchar NN`
   - `created_at timestamptz NN`
   - `google_subject varchar UQ` — unique khi khác null
   - `email_verified_at timestamptz`
   - `display_name varchar`
   - `avatar_data bytea`
   - `avatar_mime varchar`

2. `auth.refresh_tokens`
   - `id uuid PK NN`
   - `identity_id uuid FK NN -> auth.identities.id`
   - `token_hash varchar NN UQ`
   - `expires_at timestamptz NN`
   - `revoked_at timestamptz`

3. `auth.password_otps`
   - `id uuid PK NN`
   - `identity_id uuid FK NN -> auth.identities.id`
   - `otp_hash text NN`
   - `expires_at timestamptz NN`
   - `attempts int NN`
   - `used_at timestamptz`

4. `auth.email_verification_otps`
   - `id uuid PK NN`
   - `identity_id uuid FK NN -> auth.identities.id`
   - `otp_hash text NN`
   - `created_at timestamptz NN`
   - `expires_at timestamptz NN`
   - `attempts int NN`
   - `used_at timestamptz`

5. `auth.staff_account_events`
   - `id uuid PK NN`
   - `staff_identity_id uuid FK NN -> auth.identities.id`
   - `actor_identity_id uuid FK NN -> auth.identities.id`
   - `action_type varchar NN`
   - `created_at timestamptz NN`

### 3.2. Patient schema

6. `patient.patients`
   - `id uuid PK NN`
   - `identity_id uuid NN UQ REF -> auth.identities.id`
   - `full_name varchar NN`
   - `dob date`
   - `phone varchar UQ`
   - `medical_history text`
   - `allergies text`
   - `version bigint NN`
   - `created_at timestamptz NN`
   - `account_linked boolean NN`

7. `patient.ai_assessments`
   - `id uuid PK NN`
   - `patient_id uuid FK NN -> patient.patients.id`
   - `patient_identity_id uuid NN REF -> auth.identities.id`
   - `predicted_label varchar NN`
   - `confidence double precision NN`
   - `top3_json text NN`
   - `uncertain boolean NN`
   - `model_version varchar NN`
   - `shared_with_doctor boolean NN`
   - `created_at timestamptz NN`
   - `appointment_id uuid REF -> appointment.appointments.id`
   - `image_content_type varchar`
   - `image_bytes bytea`

### 3.3. Doctor schema

8. `doctor.doctors`
   - `id uuid PK NN`
   - `identity_id uuid UQ REF -> auth.identities.id`
   - `full_name varchar NN`
   - `specialty_code varchar NN`
   - `experience_years int NN`
   - `certificate_no varchar`
   - `active boolean NN`
   - `avatar_url varchar`
   - `avatar_data bytea`
   - `avatar_mime varchar`
   - `bio varchar`
   - `consultation_fee numeric NN`

9. `doctor.work_schedules`
   - `id uuid PK NN`
   - `doctor_id uuid FK NN -> doctor.doctors.id`
   - `weekday smallint NN`
   - `start_time time NN`
   - `end_time time NN`
   - `slot_minutes int NN`

10. `doctor.leave_periods`
    - `id uuid PK NN`
    - `doctor_id uuid FK NN -> doctor.doctors.id`
    - `start_at timestamptz NN`
    - `end_at timestamptz NN`
    - `reason varchar`

### 3.4. Appointment schema

11. `appointment.appointments`
    - `id uuid PK NN`
    - `patient_id uuid NN REF -> patient.patients.id`
    - `patient_identity_id uuid NN REF -> auth.identities.id`
    - `doctor_id uuid REF -> doctor.doctors.id`
    - `doctor_identity_id uuid REF -> auth.identities.id`
    - `parent_id uuid FK -> appointment.appointments.id`
    - `start_at timestamptz NN`
    - `end_at timestamptz NN`
    - `status varchar NN`
    - `reason varchar`
    - `cancel_reason varchar`
    - `idempotency_key varchar UQ`
    - `version bigint NN`
    - `created_at timestamptz NN`
    - `updated_at timestamptz NN`
    - `follow_up_reason varchar`
    - `follow_up_not_before timestamptz`
    - `patient_hidden boolean NN`
    - `hold_expires_at timestamptz`
    - `consultation_fee_snapshot numeric`
    - `checked_in_at timestamptz`

12. `appointment.appointment_notifications`
    - `id uuid PK NN`
    - `patient_identity_id uuid NN REF -> auth.identities.id`
    - `appointment_id uuid FK -> appointment.appointments.id`
    - `notification_type varchar NN`
    - `title varchar NN`
    - `body varchar NN`
    - `created_at timestamptz NN`
    - `read_at timestamptz`
    - UQ ghép: `(appointment_id, notification_type)`

13. `appointment.appointment_action_logs`
    - `id uuid PK NN`
    - `appointment_id uuid FK NN -> appointment.appointments.id`
    - `actor_identity_id uuid NN REF -> auth.identities.id`
    - `actor_role varchar NN`
    - `action_type varchar NN`
    - `created_at timestamptz NN`

14. `appointment.clinic_reviews`
    - `id uuid PK NN`
    - `appointment_id uuid FK NN UQ -> appointment.appointments.id`
    - `patient_identity_id uuid NN REF -> auth.identities.id`
    - `display_name varchar NN`
    - `rating smallint NN`
    - `comment varchar NN`
    - `status varchar NN`
    - `created_at timestamptz NN`
    - `updated_at timestamptz NN`

15. `appointment.clinic_closures`
    - `id uuid PK NN`
    - `closure_date date NN UQ`
    - `reason varchar NN`
    - `created_at timestamptz NN`

16. `appointment.reminder_actions`
    - `id uuid PK NN`
    - `appointment_id uuid FK NN -> appointment.appointments.id`
    - `receptionist_identity_id uuid NN REF -> auth.identities.id`
    - `action_type varchar NN`
    - `created_at timestamptz NN`

17. `appointment.outbox_events`
    - `id uuid PK NN`
    - `aggregate_id uuid NN REF -> appointment.appointments.id` theo loại sự kiện
    - `event_type varchar NN`
    - `payload jsonb NN`
    - `created_at timestamptz NN`
    - `published_at timestamptz`

18. `appointment.support_conversations`
    - `patient_identity_id uuid PK NN REF -> auth.identities.id`
    - `assigned_receptionist_identity_id uuid REF -> auth.identities.id`
    - `assigned_at timestamptz`
    - `updated_at timestamptz NN`
    - `channel_status varchar NN`
    - `ai_failure_count int NN`
    - `last_intent varchar`
    - `last_intent_confidence double precision`
    - `ai_summary varchar`
    - `escalation_reason varchar`
    - `escalated_at timestamptz`
    - `resolved_at timestamptz`
    - `resolved_by_identity_id uuid REF -> auth.identities.id`

19. `appointment.support_messages`
    - `id uuid PK NN`
    - `patient_identity_id uuid NN REF -> auth.identities.id`
    - `sender_identity_id uuid NN REF -> auth.identities.id`
    - `sender_role varchar NN`
    - `body varchar NN`
    - `sent_at timestamptz NN`
    - `read_at timestamptz`

### 3.5. Medical record schema

20. `medical_record.medical_records`
    - `id uuid PK NN`
    - `appointment_id uuid NN UQ REF -> appointment.appointments.id`
    - `patient_id uuid NN REF -> patient.patients.id`
    - `patient_identity_id uuid NN REF -> auth.identities.id`
    - `doctor_id uuid NN REF -> doctor.doctors.id`
    - `final_diagnosis varchar NN`
    - `clinical_notes varchar`
    - `treatment_plan varchar`
    - `severity varchar NN`
    - `follow_up_at timestamptz`
    - `signed_at timestamptz NN`
    - `version bigint NN`

21. `medical_record.patient_record_visibility`
    - `record_id uuid PK FK NN -> medical_record.medical_records.id`
    - `patient_identity_id uuid NN REF -> auth.identities.id`
    - `hidden_at timestamptz NN`

### 3.6. Prescription schema

22. `prescription.prescriptions`
    - `id uuid PK NN`
    - `record_id uuid NN UQ REF -> medical_record.medical_records.id`
    - `patient_id uuid NN REF -> patient.patients.id`
    - `patient_identity_id uuid NN REF -> auth.identities.id`
    - `doctor_id uuid NN REF -> doctor.doctors.id`
    - `instructions varchar`
    - `signed_at timestamptz NN`

23. `prescription.prescription_items`
    - `prescription_id uuid FK NN -> prescription.prescriptions.id`
    - `drug_name varchar NN`
    - `dosage varchar NN`
    - `frequency varchar`
    - `duration varchar`
    - `item_instructions varchar`
    - Bảng này là `@ElementCollection`, hiện không có PK độc lập.

### 3.7. Notification schema

24. `notification.deliveries`
    - `id uuid PK NN`
    - `event_id uuid NN UQ REF -> appointment.outbox_events.id`
    - `event_type varchar NN`
    - `recipient varchar NN`
    - `subject varchar NN`
    - `created_at timestamptz NN`
    - `sent_at timestamptz`
    - `last_error varchar`
    - `attempts int NN`

## 4. Quan hệ và lực lượng kết hợp

### Quan hệ vật lý

| Cha | Con | Cardinality |
|---|---|---|
| `identities` | `refresh_tokens` | 1 — 0..n |
| `identities` | `password_otps` | 1 — 0..n |
| `identities` | `email_verification_otps` | 1 — 0..n |
| `identities` | `staff_account_events` | 1 — 0..n, ở cả vai trò staff và actor |
| `patients` | `ai_assessments` | 1 — 0..n |
| `doctors` | `work_schedules` | 1 — 0..n |
| `doctors` | `leave_periods` | 1 — 0..n |
| `appointments` | `appointments` | 0..1 cha — 0..n lịch tái khám/con |
| `appointments` | `appointment_notifications` | 1 — 0..n |
| `appointments` | `appointment_action_logs` | 1 — 0..n |
| `appointments` | `clinic_reviews` | 1 — 0..1 |
| `appointments` | `reminder_actions` | 1 — 0..n |
| `medical_records` | `patient_record_visibility` | 1 — 0..1 |
| `prescriptions` | `prescription_items` | 1 — 0..n |

### Quan hệ logic giữa microservice

| Cha | Con | Cardinality | Trường liên kết |
|---|---|---|---|
| `identities` | `patients` | 1 — 0..1 | `identity_id` |
| `identities` | `doctors` | 1 — 0..1 | `identity_id` |
| `patients` | `appointments` | 1 — 0..n | `patient_id` |
| `doctors` | `appointments` | 0..1 — 0..n | `doctor_id` |
| `appointments` | `ai_assessments` | 1 — 0..1 ảnh được chia sẻ | `appointment_id` |
| `appointments` | `medical_records` | 1 — 0..1 | `appointment_id` |
| `patients` | `medical_records` | 1 — 0..n | `patient_id` |
| `doctors` | `medical_records` | 1 — 0..n | `doctor_id` |
| `medical_records` | `prescriptions` | 1 — 0..1 | `record_id` |
| `patients` | `prescriptions` | 1 — 0..n | `patient_id` |
| `doctors` | `prescriptions` | 1 — 0..n | `doctor_id` |
| `support_conversations` | `support_messages` | 1 — 0..n | `patient_identity_id` |
| `outbox_events` | `deliveries` | 1 — 0..1 | `id -> event_id` |

## 5. Constraint quan trọng phải thể hiện trong thuyết minh

- Một bác sĩ không thể có hai lịch hoạt động chồng thời gian: exclusion constraint
  `no_doctor_overlap`.
- Một bệnh nhân không thể có hai lịch hoạt động chồng thời gian: exclusion constraint
  `no_patient_overlap`.
- `appointments.start_at < appointments.end_at`.
- `consultation_fee` và `consultation_fee_snapshot` không âm.
- Lịch đã có `doctor_id` phải có `consultation_fee_snapshot`.
- Một cuộc hẹn chỉ có tối đa một đánh giá và một hồ sơ y khoa.
- Một hồ sơ y khoa chỉ có tối đa một đơn thuốc.
- `clinic_reviews.rating` nằm trong khoảng 1–5.
- `work_schedules.weekday` nằm trong khoảng 1–7; `slot_minutes` từ 10–120.
- `ai_assessments.confidence` nằm trong khoảng 0–1.
- Số điện thoại bệnh nhân sau chuẩn hóa phải khớp `^0[0-9]{8,10}$` và là duy nhất.

## 6. Enum dùng trong class diagram

- `Role`: `ADMIN`, `RECEPTIONIST`, `DOCTOR`, `PATIENT`.
- `IdentityStatus`: `PENDING`, `ACTIVE`, `LOCKED`, `DISABLED`.
- `AppointmentStatus`: `HELD`, `PROPOSED`, `PENDING`, `ASSIGNED`, `CONFIRMED`,
  `CHECKED_IN`, `IN_PROGRESS`, `COMPLETED`, `FOLLOW_UP_REQUIRED`, `NO_SHOW`,
  `CANCELLED`.
- `ReviewStatus`: `PENDING`, `APPROVED`, `HIDDEN`.
- `Severity`: `MILD`, `MODERATE`, `SEVERE`, `URGENT`.

## 7. Cách dùng

Mở `database-erd.puml` và `database-class.puml` bằng PlantUML để xuất PNG/SVG. Khi
vẽ thủ công, dùng đường liền cho FK vật lý và đường nét đứt cho `REF` logic. Cách thể hiện
này phản ánh đúng kiến trúc microservice: mỗi service sở hữu schema riêng, còn liên kết
chéo service được kiểm tra qua API thay vì FK xuyên schema.
