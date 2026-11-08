# Tham chiếu database DermAI Clinic

Tài liệu này được sinh từ PostgreSQL của môi trường local. Nó liệt kê toàn bộ bảng nghiệp vụ,
cột, ràng buộc và chỉ mục vật lý tại thời điểm tạo. `flyway_schema_history` được loại khỏi bảng nghiệp vụ.
Mã nguồn tạo schema mới nằm trong `services/*/src/main/resources/db/migration`,
`services/inventory-service/db/migration` và
`database/dermai_full_schema.sql`. Chạy lại lệnh ở đầu
`scripts/generate_database_reference.py` khi migration thay đổi.

## Tổng quan

| Schema | Số bảng nghiệp vụ |
|---|---:|
| `auth` | 5 |
| `patient` | 4 |
| `doctor` | 7 |
| `appointment` | 11 |
| `payment` | 4 |
| `medical_record` | 2 |
| `prescription` | 9 |
| `pharmacy` | 5 |
| `notification` | 1 |
| **Tổng** | **48** |

## Bảng và cột

### `auth`

#### `auth.email_verification_otps`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `identity_id` | `uuid` | Không | — |
| `otp_hash` | `text` | Không | — |
| `created_at` | `timestamp with time zone` | Không | — |
| `expires_at` | `timestamp with time zone` | Không | — |
| `attempts` | `integer` | Không | `0` |
| `used_at` | `timestamp with time zone` | Có | — |

Ràng buộc:

- **FK** `email_verification_otps_identity_id_fkey`: `FOREIGN KEY (identity_id) REFERENCES auth.identities(id) ON DELETE CASCADE`
- **PK** `email_verification_otps_pkey`: `PRIMARY KEY (id)`

Chỉ mục bổ sung:

- `ix_email_verification_identity_created`: `CREATE INDEX ix_email_verification_identity_created ON auth.email_verification_otps USING btree (identity_id, created_at DESC)`

#### `auth.identities`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `email` | `character varying(320)` | Không | — |
| `password_hash` | `text` | Có | — |
| `role` | `character varying(20)` | Không | — |
| `status` | `character varying(20)` | Không | — |
| `created_at` | `timestamp with time zone` | Không | `now()` |
| `google_subject` | `character varying(255)` | Có | — |
| `email_verified_at` | `timestamp with time zone` | Có | — |
| `display_name` | `character varying(150)` | Có | — |
| `avatar_data` | `bytea` | Có | — |
| `avatar_mime` | `character varying(50)` | Có | — |

Ràng buộc:

- **PK** `identities_pkey`: `PRIMARY KEY (id)`
- **UNIQUE** `identities_email_key`: `UNIQUE (email)`

Chỉ mục bổ sung:

- `ux_identities_google_subject`: `CREATE UNIQUE INDEX ux_identities_google_subject ON auth.identities USING btree (google_subject) WHERE (google_subject IS NOT NULL)`

#### `auth.password_otps`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `identity_id` | `uuid` | Không | — |
| `otp_hash` | `text` | Không | — |
| `expires_at` | `timestamp with time zone` | Không | — |
| `attempts` | `integer` | Không | `0` |
| `used_at` | `timestamp with time zone` | Có | — |

Ràng buộc:

- **FK** `password_otps_identity_id_fkey`: `FOREIGN KEY (identity_id) REFERENCES auth.identities(id) ON DELETE CASCADE`
- **PK** `password_otps_pkey`: `PRIMARY KEY (id)`

Chỉ mục bổ sung:

- `ix_otp_identity_expiry`: `CREATE INDEX ix_otp_identity_expiry ON auth.password_otps USING btree (identity_id, expires_at DESC)`

#### `auth.refresh_tokens`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `identity_id` | `uuid` | Không | — |
| `token_hash` | `character varying(64)` | Không | — |
| `expires_at` | `timestamp with time zone` | Không | — |
| `revoked_at` | `timestamp with time zone` | Có | — |

Ràng buộc:

- **FK** `refresh_tokens_identity_id_fkey`: `FOREIGN KEY (identity_id) REFERENCES auth.identities(id) ON DELETE CASCADE`
- **PK** `refresh_tokens_pkey`: `PRIMARY KEY (id)`
- **UNIQUE** `refresh_tokens_token_hash_key`: `UNIQUE (token_hash)`

Chỉ mục bổ sung:

- `ix_refresh_identity`: `CREATE INDEX ix_refresh_identity ON auth.refresh_tokens USING btree (identity_id)`

#### `auth.staff_account_events`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `staff_identity_id` | `uuid` | Không | — |
| `actor_identity_id` | `uuid` | Không | — |
| `action_type` | `character varying(40)` | Không | — |
| `created_at` | `timestamp with time zone` | Không | `now()` |

Ràng buộc:

- **FK** `staff_account_events_actor_identity_id_fkey`: `FOREIGN KEY (actor_identity_id) REFERENCES auth.identities(id)`
- **FK** `staff_account_events_staff_identity_id_fkey`: `FOREIGN KEY (staff_identity_id) REFERENCES auth.identities(id)`
- **PK** `staff_account_events_pkey`: `PRIMARY KEY (id)`

Chỉ mục bổ sung:

- `ix_staff_account_events_staff_created`: `CREATE INDEX ix_staff_account_events_staff_created ON auth.staff_account_events USING btree (staff_identity_id, created_at DESC)`

### `patient`

#### `patient.ai_access_audit_logs`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `assessment_id` | `uuid` | Có | — |
| `patient_identity_id` | `uuid` | Có | — |
| `actor_identity_id` | `uuid` | Không | — |
| `actor_role` | `character varying(20)` | Không | — |
| `action_type` | `character varying(50)` | Không | — |
| `source_ip` | `character varying(64)` | Có | — |
| `user_agent` | `character varying(500)` | Có | — |
| `created_at` | `timestamp with time zone` | Không | `now()` |

Ràng buộc:

- **PK** `ai_access_audit_logs_pkey`: `PRIMARY KEY (id)`

Chỉ mục bổ sung:

- `ix_ai_access_audit_actor_created`: `CREATE INDEX ix_ai_access_audit_actor_created ON patient.ai_access_audit_logs USING btree (actor_identity_id, created_at DESC)`

#### `patient.ai_assessments`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `patient_id` | `uuid` | Không | — |
| `patient_identity_id` | `uuid` | Không | — |
| `predicted_label` | `character varying(80)` | Không | — |
| `confidence` | `double precision` | Không | — |
| `top3_json` | `text` | Không | — |
| `uncertain` | `boolean` | Không | `false` |
| `model_version` | `character varying(120)` | Không | — |
| `shared_with_doctor` | `boolean` | Không | `false` |
| `created_at` | `timestamp with time zone` | Không | `now()` |
| `appointment_id` | `uuid` | Có | — |
| `image_content_type` | `character varying(80)` | Có | — |
| `image_bytes` | `bytea` | Có | — |
| `consent_event_id` | `uuid` | Có | — |
| `image_retention_until` | `timestamp with time zone` | Có | — |
| `deleted_at` | `timestamp with time zone` | Có | — |

Ràng buộc:

- **CHECK** `ai_assessments_confidence_check`: `CHECK (confidence >= 0::double precision AND confidence <= 1::double precision)`
- **FK** `ai_assessments_consent_event_id_fkey`: `FOREIGN KEY (consent_event_id) REFERENCES patient.ai_consent_events(id)`
- **FK** `ai_assessments_patient_id_fkey`: `FOREIGN KEY (patient_id) REFERENCES patient.patients(id) ON DELETE CASCADE`
- **PK** `ai_assessments_pkey`: `PRIMARY KEY (id)`

Chỉ mục bổ sung:

- `ix_ai_assessments_image_retention`: `CREATE INDEX ix_ai_assessments_image_retention ON patient.ai_assessments USING btree (image_retention_until) WHERE (image_bytes IS NOT NULL)`
- `ix_ai_assessments_patient_created`: `CREATE INDEX ix_ai_assessments_patient_created ON patient.ai_assessments USING btree (patient_identity_id, created_at DESC)`
- `ux_ai_assessments_shared_appointment`: `CREATE UNIQUE INDEX ux_ai_assessments_shared_appointment ON patient.ai_assessments USING btree (appointment_id) WHERE ((appointment_id IS NOT NULL) AND (shared_with_doctor = true))`

#### `patient.ai_consent_events`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `patient_identity_id` | `uuid` | Không | — |
| `purpose` | `character varying(80)` | Không | — |
| `policy_version` | `character varying(40)` | Không | — |
| `granted_at` | `timestamp with time zone` | Không | `now()` |

Ràng buộc:

- **PK** `ai_consent_events_pkey`: `PRIMARY KEY (id)`

#### `patient.patients`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `identity_id` | `uuid` | Không | — |
| `full_name` | `character varying(160)` | Không | — |
| `dob` | `date` | Có | — |
| `phone` | `character varying(30)` | Có | — |
| `medical_history` | `text` | Có | — |
| `allergies` | `text` | Có | — |
| `version` | `bigint` | Không | `0` |
| `created_at` | `timestamp with time zone` | Không | `now()` |
| `account_linked` | `boolean` | Không | `true` |

Ràng buộc:

- **CHECK** `ck_patients_phone_vietnam`: `CHECK (phone IS NULL OR phone::text ~ '^0[0-9]{8,10}$'::text)`
- **PK** `patients_pkey`: `PRIMARY KEY (id)`
- **UNIQUE** `patients_identity_id_key`: `UNIQUE (identity_id)`

Chỉ mục bổ sung:

- `ix_patient_name`: `CREATE INDEX ix_patient_name ON patient.patients USING btree (lower((full_name)::text))`
- `uq_patients_phone`: `CREATE UNIQUE INDEX uq_patients_phone ON patient.patients USING btree (phone) WHERE (phone IS NOT NULL)`

### `doctor`

#### `doctor.clinic_service_doctors`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `service_id` | `uuid` | Không | — |
| `doctor_id` | `uuid` | Không | — |

Ràng buộc:

- **FK** `clinic_service_doctors_doctor_id_fkey`: `FOREIGN KEY (doctor_id) REFERENCES doctor.doctors(id) ON DELETE CASCADE`
- **FK** `clinic_service_doctors_service_id_fkey`: `FOREIGN KEY (service_id) REFERENCES doctor.clinic_services(id) ON DELETE CASCADE`
- **PK** `clinic_service_doctors_pkey`: `PRIMARY KEY (service_id, doctor_id)`

Chỉ mục bổ sung:

- `ix_clinic_service_doctors_doctor`: `CREATE INDEX ix_clinic_service_doctors_doctor ON doctor.clinic_service_doctors USING btree (doctor_id, service_id)`

#### `doctor.clinic_services`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `code` | `character varying(80)` | Không | — |
| `name` | `character varying(160)` | Không | — |
| `description` | `character varying(1000)` | Không | — |
| `price_from` | `numeric(12,0)` | Không | — |
| `duration_minutes` | `integer` | Không | — |
| `display_order` | `integer` | Không | `0` |
| `active` | `boolean` | Không | `true` |
| `specialty_code` | `character varying(80)` | Không | — |

Ràng buộc:

- **CHECK** `clinic_services_duration_minutes_check`: `CHECK (duration_minutes >= 10 AND duration_minutes <= 240)`
- **CHECK** `clinic_services_price_from_check`: `CHECK (price_from >= 0::numeric)`
- **PK** `clinic_services_pkey`: `PRIMARY KEY (id)`
- **UNIQUE** `clinic_services_code_key`: `UNIQUE (code)`

Chỉ mục bổ sung:

- `ix_clinic_services_specialty_active`: `CREATE INDEX ix_clinic_services_specialty_active ON doctor.clinic_services USING btree (upper(TRIM(BOTH FROM specialty_code)), display_order) WHERE active`

#### `doctor.doctors`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `identity_id` | `uuid` | Có | — |
| `full_name` | `character varying(160)` | Không | — |
| `specialty_code` | `character varying(80)` | Không | — |
| `experience_years` | `integer` | Không | — |
| `certificate_no` | `character varying(100)` | Có | — |
| `active` | `boolean` | Không | `true` |
| `avatar_url` | `character varying(500)` | Có | — |
| `avatar_data` | `bytea` | Có | — |
| `avatar_mime` | `character varying(50)` | Có | — |
| `bio` | `character varying(1200)` | Có | — |
| `consultation_fee` | `numeric(12,0)` | Không | — |
| `phone` | `character varying(20)` | Có | — |

Ràng buộc:

- **CHECK** `ck_doctor_consultation_fee_non_negative`: `CHECK (consultation_fee >= 0::numeric)`
- **CHECK** `doctors_experience_years_check`: `CHECK (experience_years >= 0)`
- **PK** `doctors_pkey`: `PRIMARY KEY (id)`
- **UNIQUE** `doctors_identity_id_key`: `UNIQUE (identity_id)`

Chỉ mục bổ sung:

- `ix_doctor_specialty`: `CREATE INDEX ix_doctor_specialty ON doctor.doctors USING btree (specialty_code) WHERE active`

#### `doctor.leave_approval_views`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `leave_id` | `uuid` | Không | — |
| `receptionist_identity_id` | `uuid` | Không | — |
| `viewed_at` | `timestamp with time zone` | Không | `now()` |

Ràng buộc:

- **FK** `leave_approval_views_leave_id_fkey`: `FOREIGN KEY (leave_id) REFERENCES doctor.leave_periods(id) ON DELETE CASCADE`
- **PK** `leave_approval_views_pkey`: `PRIMARY KEY (id)`
- **UNIQUE** `uq_leave_approval_view`: `UNIQUE (leave_id, receptionist_identity_id)`

Chỉ mục bổ sung:

- `ix_leave_approval_view_receptionist`: `CREATE INDEX ix_leave_approval_view_receptionist ON doctor.leave_approval_views USING btree (receptionist_identity_id, viewed_at)`

#### `doctor.leave_periods`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `doctor_id` | `uuid` | Không | — |
| `start_at` | `timestamp with time zone` | Không | — |
| `end_at` | `timestamp with time zone` | Không | — |
| `reason` | `character varying(250)` | Có | — |
| `status` | `character varying(20)` | Không | `'APPROVED'::character varying` |
| `requested_by` | `uuid` | Có | — |
| `reviewed_by` | `uuid` | Có | — |
| `reviewed_at` | `timestamp with time zone` | Có | — |
| `review_note` | `character varying(250)` | Có | — |

Ràng buộc:

- **CHECK** `ck_leave_period_status`: `CHECK (status::text = ANY (ARRAY['PENDING'::character varying, 'APPROVED'::character varying, 'REJECTED'::character varying]::text[]))`
- **CHECK** `leave_periods_check`: `CHECK (start_at < end_at)`
- **FK** `leave_periods_doctor_id_fkey`: `FOREIGN KEY (doctor_id) REFERENCES doctor.doctors(id) ON DELETE CASCADE`
- **PK** `leave_periods_pkey`: `PRIMARY KEY (id)`

Chỉ mục bổ sung:

- `ix_leave_doctor_time`: `CREATE INDEX ix_leave_doctor_time ON doctor.leave_periods USING btree (doctor_id, start_at, end_at)`
- `ix_leave_status_time`: `CREATE INDEX ix_leave_status_time ON doctor.leave_periods USING btree (status, start_at, end_at)`

#### `doctor.slot_duration_policies`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `doctor_id` | `uuid` | Không | — |
| `effective_from` | `date` | Không | — |
| `slot_minutes` | `integer` | Không | — |

Ràng buộc:

- **CHECK** `slot_duration_policies_slot_minutes_check`: `CHECK (slot_minutes >= 10 AND slot_minutes <= 120)`
- **FK** `slot_duration_policies_doctor_id_fkey`: `FOREIGN KEY (doctor_id) REFERENCES doctor.doctors(id) ON DELETE CASCADE`
- **PK** `slot_duration_policies_pkey`: `PRIMARY KEY (id)`
- **UNIQUE** `slot_duration_policies_doctor_id_effective_from_key`: `UNIQUE (doctor_id, effective_from)`

Chỉ mục bổ sung:

- `ix_slot_duration_policy_doctor_date`: `CREATE INDEX ix_slot_duration_policy_doctor_date ON doctor.slot_duration_policies USING btree (doctor_id, effective_from DESC)`

#### `doctor.work_schedules`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `doctor_id` | `uuid` | Không | — |
| `weekday` | `smallint` | Không | — |
| `start_time` | `time without time zone` | Không | — |
| `end_time` | `time without time zone` | Không | — |
| `slot_minutes` | `integer` | Không | — |

Ràng buộc:

- **CHECK** `work_schedules_check`: `CHECK (start_time < end_time)`
- **CHECK** `work_schedules_slot_minutes_check`: `CHECK (slot_minutes >= 10 AND slot_minutes <= 120)`
- **CHECK** `work_schedules_weekday_check`: `CHECK (weekday >= 1 AND weekday <= 7)`
- **FK** `work_schedules_doctor_id_fkey`: `FOREIGN KEY (doctor_id) REFERENCES doctor.doctors(id) ON DELETE CASCADE`
- **PK** `work_schedules_pkey`: `PRIMARY KEY (id)`
- **UNIQUE** `work_schedules_doctor_id_weekday_start_time_end_time_key`: `UNIQUE (doctor_id, weekday, start_time, end_time)`

### `appointment`

#### `appointment.appointment_action_logs`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `appointment_id` | `uuid` | Không | — |
| `actor_identity_id` | `uuid` | Không | — |
| `actor_role` | `character varying(20)` | Không | — |
| `action_type` | `character varying(50)` | Không | — |
| `created_at` | `timestamp with time zone` | Không | `now()` |

Ràng buộc:

- **FK** `appointment_action_logs_appointment_id_fkey`: `FOREIGN KEY (appointment_id) REFERENCES appointment.appointments(id) ON DELETE CASCADE`
- **PK** `appointment_action_logs_pkey`: `PRIMARY KEY (id)`

Chỉ mục bổ sung:

- `ix_appointment_action_actor_created`: `CREATE INDEX ix_appointment_action_actor_created ON appointment.appointment_action_logs USING btree (actor_identity_id, created_at DESC)`
- `ix_appointment_action_appointment_created`: `CREATE INDEX ix_appointment_action_appointment_created ON appointment.appointment_action_logs USING btree (appointment_id, created_at DESC)`

#### `appointment.appointment_notifications`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `patient_identity_id` | `uuid` | Không | — |
| `appointment_id` | `uuid` | Có | — |
| `notification_type` | `character varying(100)` | Không | — |
| `title` | `character varying(160)` | Không | — |
| `body` | `character varying(500)` | Không | — |
| `created_at` | `timestamp with time zone` | Không | `now()` |
| `read_at` | `timestamp with time zone` | Có | — |

Ràng buộc:

- **FK** `appointment_notifications_appointment_id_fkey`: `FOREIGN KEY (appointment_id) REFERENCES appointment.appointments(id) ON DELETE CASCADE`
- **PK** `appointment_notifications_pkey`: `PRIMARY KEY (id)`
- **UNIQUE** `appointment_notifications_appointment_id_notification_type_key`: `UNIQUE (appointment_id, notification_type)`

Chỉ mục bổ sung:

- `ix_notification_patient`: `CREATE INDEX ix_notification_patient ON appointment.appointment_notifications USING btree (patient_identity_id, created_at DESC)`

#### `appointment.appointment_performed_services`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `appointment_id` | `uuid` | Không | — |
| `service_id` | `uuid` | Không | — |
| `service_code` | `character varying(80)` | Không | — |
| `service_name` | `character varying(160)` | Không | — |
| `unit_price` | `numeric(12,0)` | Không | — |
| `confirmed_by` | `uuid` | Không | — |
| `confirmed_at` | `timestamp with time zone` | Không | — |

Ràng buộc:

- **CHECK** `appointment_performed_services_unit_price_check`: `CHECK (unit_price >= 0::numeric)`
- **FK** `appointment_performed_services_appointment_id_fkey`: `FOREIGN KEY (appointment_id) REFERENCES appointment.appointments(id) ON DELETE CASCADE`
- **PK** `appointment_performed_services_pkey`: `PRIMARY KEY (id)`
- **UNIQUE** `uq_appointment_performed_service`: `UNIQUE (appointment_id, service_id)`

Chỉ mục bổ sung:

- `ix_appointment_performed_services_appointment`: `CREATE INDEX ix_appointment_performed_services_appointment ON appointment.appointment_performed_services USING btree (appointment_id)`

#### `appointment.appointments`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `patient_id` | `uuid` | Không | — |
| `patient_identity_id` | `uuid` | Không | — |
| `doctor_id` | `uuid` | Có | — |
| `doctor_identity_id` | `uuid` | Có | — |
| `parent_id` | `uuid` | Có | — |
| `start_at` | `timestamp with time zone` | Không | — |
| `end_at` | `timestamp with time zone` | Không | — |
| `status` | `character varying(30)` | Không | — |
| `reason` | `character varying(500)` | Có | — |
| `cancel_reason` | `character varying(500)` | Có | — |
| `idempotency_key` | `character varying(100)` | Có | — |
| `version` | `bigint` | Không | `0` |
| `created_at` | `timestamp with time zone` | Không | `now()` |
| `updated_at` | `timestamp with time zone` | Không | `now()` |
| `follow_up_reason` | `character varying(500)` | Có | — |
| `follow_up_not_before` | `timestamp with time zone` | Có | — |
| `patient_hidden` | `boolean` | Không | `false` |
| `hold_expires_at` | `timestamp with time zone` | Có | — |
| `consultation_fee_snapshot` | `numeric(12,0)` | Có | — |
| `checked_in_at` | `timestamp with time zone` | Có | — |
| `payment_method` | `character varying(30)` | Có | — |
| `payment_override_reason` | `character varying(500)` | Có | — |
| `cancellation_initiator` | `character varying(30)` | Có | — |
| `services_confirmed_at` | `timestamp with time zone` | Có | — |
| `services_confirmed_by` | `uuid` | Có | — |

Ràng buộc:

- **CHECK** `appointments_check`: `CHECK (start_at < end_at)`
- **CHECK** `ck_appointment_consultation_fee_snapshot_non_negative`: `CHECK (consultation_fee_snapshot IS NULL OR consultation_fee_snapshot >= 0::numeric)`
- **CHECK** `ck_appointment_doctor_fee_pair`: `CHECK (doctor_id IS NULL OR consultation_fee_snapshot IS NOT NULL)`
- **FK** `appointments_parent_id_fkey`: `FOREIGN KEY (parent_id) REFERENCES appointment.appointments(id)`
- **PK** `appointments_pkey`: `PRIMARY KEY (id)`
- **UNIQUE** `appointments_idempotency_key_key`: `UNIQUE (idempotency_key)`
- **EXCLUDE** `no_doctor_overlap`: `EXCLUDE USING gist (doctor_id WITH =, tstzrange(start_at, end_at, '[)'::text) WITH &&) WHERE (doctor_id IS NOT NULL AND (status::text = ANY (ARRAY['HELD'::character varying, 'PROPOSED'::character varying, 'PENDING'::character varying, 'ASSIGNED'::character varying, 'PENDING_PAYMENT'::character varying, 'PENDING_CONFIRMATION'::character varying, 'CONFIRMED'::character varying, 'CHECKED_IN'::character varying, 'IN_PROGRESS'::character varying]::text[])))`
- **EXCLUDE** `no_patient_overlap`: `EXCLUDE USING gist (patient_identity_id WITH =, tstzrange(start_at, end_at, '[)'::text) WITH &&) WHERE (status::text = ANY (ARRAY['HELD'::character varying, 'PROPOSED'::character varying, 'PENDING'::character varying, 'ASSIGNED'::character varying, 'PENDING_PAYMENT'::character varying, 'PENDING_CONFIRMATION'::character varying, 'CONFIRMED'::character varying, 'CHECKED_IN'::character varying, 'IN_PROGRESS'::character varying]::text[]))`

Chỉ mục bổ sung:

- `idx_appointments_checked_in_at`: `CREATE INDEX idx_appointments_checked_in_at ON appointment.appointments USING btree (checked_in_at) WHERE (checked_in_at IS NOT NULL)`
- `ix_appointment_doctor`: `CREATE INDEX ix_appointment_doctor ON appointment.appointments USING btree (doctor_id, start_at) WHERE ((status)::text <> 'CANCELLED'::text)`
- `ix_appointment_doctor_identity`: `CREATE INDEX ix_appointment_doctor_identity ON appointment.appointments USING btree (doctor_identity_id, start_at) WHERE ((status)::text <> 'CANCELLED'::text)`
- `ix_appointment_patient`: `CREATE INDEX ix_appointment_patient ON appointment.appointments USING btree (patient_id, start_at DESC)`
- `ix_appointment_patient_identity`: `CREATE INDEX ix_appointment_patient_identity ON appointment.appointments USING btree (patient_identity_id, start_at DESC)`
- `ix_expiring_holds`: `CREATE INDEX ix_expiring_holds ON appointment.appointments USING btree (hold_expires_at) WHERE ((status)::text = 'HELD'::text)`
- `ix_expiring_proposals`: `CREATE INDEX ix_expiring_proposals ON appointment.appointments USING btree (hold_expires_at) WHERE ((status)::text = 'PROPOSED'::text)`

#### `appointment.clinic_closures`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `closure_date` | `date` | Không | — |
| `reason` | `character varying(300)` | Không | — |
| `created_at` | `timestamp with time zone` | Không | `now()` |

Ràng buộc:

- **PK** `clinic_closures_pkey`: `PRIMARY KEY (id)`
- **UNIQUE** `clinic_closures_closure_date_key`: `UNIQUE (closure_date)`

#### `appointment.clinic_reviews`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `appointment_id` | `uuid` | Không | — |
| `patient_identity_id` | `uuid` | Không | — |
| `display_name` | `character varying(120)` | Không | — |
| `rating` | `smallint` | Không | — |
| `comment` | `character varying(1000)` | Không | — |
| `status` | `character varying(20)` | Không | `'PENDING'::character varying` |
| `created_at` | `timestamp with time zone` | Không | `now()` |
| `updated_at` | `timestamp with time zone` | Không | `now()` |

Ràng buộc:

- **CHECK** `clinic_reviews_rating_check`: `CHECK (rating >= 1 AND rating <= 5)`
- **FK** `clinic_reviews_appointment_id_fkey`: `FOREIGN KEY (appointment_id) REFERENCES appointment.appointments(id)`
- **PK** `clinic_reviews_pkey`: `PRIMARY KEY (id)`
- **UNIQUE** `clinic_reviews_appointment_id_key`: `UNIQUE (appointment_id)`

Chỉ mục bổ sung:

- `ix_clinic_reviews_status`: `CREATE INDEX ix_clinic_reviews_status ON appointment.clinic_reviews USING btree (status, created_at DESC)`

#### `appointment.outbox_events`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `aggregate_id` | `uuid` | Không | — |
| `event_type` | `character varying(120)` | Không | — |
| `payload` | `jsonb` | Không | — |
| `created_at` | `timestamp with time zone` | Không | `now()` |
| `published_at` | `timestamp with time zone` | Có | — |

Ràng buộc:

- **PK** `outbox_events_pkey`: `PRIMARY KEY (id)`

Chỉ mục bổ sung:

- `ix_outbox_pending`: `CREATE INDEX ix_outbox_pending ON appointment.outbox_events USING btree (created_at) WHERE (published_at IS NULL)`

#### `appointment.reception_notifications`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `appointment_id` | `uuid` | Không | — |
| `patient_identity_id` | `uuid` | Không | — |
| `notification_type` | `character varying(100)` | Không | — |
| `title` | `character varying(160)` | Không | — |
| `body` | `character varying(500)` | Không | — |
| `created_at` | `timestamp with time zone` | Không | `now()` |
| `read_at` | `timestamp with time zone` | Có | — |

Ràng buộc:

- **FK** `reception_notifications_appointment_id_fkey`: `FOREIGN KEY (appointment_id) REFERENCES appointment.appointments(id) ON DELETE CASCADE`
- **PK** `reception_notifications_pkey`: `PRIMARY KEY (id)`
- **UNIQUE** `reception_notifications_appointment_id_notification_type_key`: `UNIQUE (appointment_id, notification_type)`

Chỉ mục bổ sung:

- `ix_reception_notification_created`: `CREATE INDEX ix_reception_notification_created ON appointment.reception_notifications USING btree (created_at DESC)`

#### `appointment.reminder_actions`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `appointment_id` | `uuid` | Không | — |
| `receptionist_identity_id` | `uuid` | Không | — |
| `action_type` | `character varying(30)` | Không | — |
| `created_at` | `timestamp with time zone` | Không | `now()` |

Ràng buộc:

- **FK** `reminder_actions_appointment_id_fkey`: `FOREIGN KEY (appointment_id) REFERENCES appointment.appointments(id) ON DELETE CASCADE`
- **PK** `reminder_actions_pkey`: `PRIMARY KEY (id)`

Chỉ mục bổ sung:

- `ix_reminder_action_appointment`: `CREATE INDEX ix_reminder_action_appointment ON appointment.reminder_actions USING btree (appointment_id, created_at DESC)`

#### `appointment.support_conversations`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `patient_identity_id` | `uuid` | Không | — |
| `assigned_receptionist_identity_id` | `uuid` | Có | — |
| `assigned_at` | `timestamp with time zone` | Có | — |
| `updated_at` | `timestamp with time zone` | Không | `now()` |
| `channel_status` | `character varying(30)` | Không | `'WAITING_RECEPTIONIST'::character varying` |
| `ai_failure_count` | `integer` | Không | `0` |
| `last_intent` | `character varying(80)` | Có | — |
| `last_intent_confidence` | `double precision` | Có | — |
| `ai_summary` | `character varying(4000)` | Có | — |
| `escalation_reason` | `character varying(120)` | Có | — |
| `escalated_at` | `timestamp with time zone` | Có | — |
| `resolved_at` | `timestamp with time zone` | Có | — |
| `resolved_by_identity_id` | `uuid` | Có | — |

Ràng buộc:

- **PK** `support_conversations_pkey`: `PRIMARY KEY (patient_identity_id)`

Chỉ mục bổ sung:

- `ix_support_conversations_assignee_updated`: `CREATE INDEX ix_support_conversations_assignee_updated ON appointment.support_conversations USING btree (assigned_receptionist_identity_id, updated_at DESC)`
- `ix_support_conversations_status_updated`: `CREATE INDEX ix_support_conversations_status_updated ON appointment.support_conversations USING btree (channel_status, updated_at DESC)`

#### `appointment.support_messages`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `patient_identity_id` | `uuid` | Không | — |
| `sender_identity_id` | `uuid` | Không | — |
| `sender_role` | `character varying(30)` | Không | — |
| `body` | `character varying(2000)` | Không | — |
| `sent_at` | `timestamp with time zone` | Không | — |
| `read_at` | `timestamp with time zone` | Có | — |
| `attachment_content_type` | `character varying(50)` | Có | — |
| `attachment_original_name` | `character varying(255)` | Có | — |
| `attachment_size_bytes` | `bigint` | Có | — |
| `attachment_data` | `bytea` | Có | — |

Ràng buộc:

- **PK** `support_messages_pkey`: `PRIMARY KEY (id)`

Chỉ mục bổ sung:

- `ix_support_patient_time`: `CREATE INDEX ix_support_patient_time ON appointment.support_messages USING btree (patient_identity_id, sent_at)`

### `payment`

#### `payment.deposit_settings`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `integer` | Không | — |
| `amount` | `numeric(12,0)` | Không | — |
| `updated_at` | `timestamp with time zone` | Không | `now()` |
| `updated_by` | `uuid` | Có | — |

Ràng buộc:

- **CHECK** `deposit_settings_amount_check`: `CHECK (amount >= 1000::numeric AND amount <= 100000000::numeric)`
- **CHECK** `deposit_settings_id_check`: `CHECK (id = 1)`
- **PK** `deposit_settings_pkey`: `PRIMARY KEY (id)`

#### `payment.invoice_payments`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `invoice_id` | `uuid` | Không | — |
| `patient_identity_id` | `uuid` | Không | — |
| `amount` | `numeric(12,0)` | Không | — |
| `order_code` | `bigint` | Không | — |
| `status` | `character varying(30)` | Không | — |
| `payos_trans_id` | `character varying(255)` | Có | — |
| `payment_link_id` | `character varying(255)` | Có | — |
| `checkout_url` | `text` | Có | — |
| `qr_code` | `text` | Có | — |
| `expires_at` | `timestamp with time zone` | Không | — |
| `created_at` | `timestamp with time zone` | Không | — |
| `updated_at` | `timestamp with time zone` | Không | — |
| `version` | `bigint` | Không | `0` |

Ràng buộc:

- **CHECK** `invoice_payments_amount_check`: `CHECK (amount > 0::numeric)`
- **PK** `invoice_payments_pkey`: `PRIMARY KEY (id)`
- **UNIQUE** `invoice_payments_invoice_id_key`: `UNIQUE (invoice_id)`
- **UNIQUE** `invoice_payments_order_code_key`: `UNIQUE (order_code)`
- **UNIQUE** `invoice_payments_payment_link_id_key`: `UNIQUE (payment_link_id)`
- **UNIQUE** `invoice_payments_payos_trans_id_key`: `UNIQUE (payos_trans_id)`

Chỉ mục bổ sung:

- `idx_invoice_payments_patient`: `CREATE INDEX idx_invoice_payments_patient ON payment.invoice_payments USING btree (patient_identity_id, created_at DESC)`

#### `payment.payment_outbox_events`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `aggregate_id` | `uuid` | Không | — |
| `routing_key` | `character varying(100)` | Không | — |
| `payload` | `jsonb` | Không | — |
| `created_at` | `timestamp with time zone` | Không | `now()` |
| `published_at` | `timestamp with time zone` | Có | — |

Ràng buộc:

- **PK** `payment_outbox_events_pkey`: `PRIMARY KEY (id)`
- **UNIQUE** `payment_outbox_events_aggregate_id_routing_key_key`: `UNIQUE (aggregate_id, routing_key)`

Chỉ mục bổ sung:

- `ix_payment_outbox_pending`: `CREATE INDEX ix_payment_outbox_pending ON payment.payment_outbox_events USING btree (created_at) WHERE (published_at IS NULL)`

#### `payment.payments`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `booking_id` | `uuid` | Không | — |
| `patient_identity_id` | `uuid` | Không | — |
| `amount` | `numeric(12,0)` | Không | — |
| `order_code` | `bigint` | Không | — |
| `status` | `character varying(30)` | Không | — |
| `payos_trans_id` | `character varying(100)` | Có | — |
| `payment_link_id` | `character varying(100)` | Có | — |
| `checkout_url` | `text` | Có | — |
| `qr_code` | `text` | Có | — |
| `appointment_start_at` | `timestamp with time zone` | Không | — |
| `expires_at` | `timestamp with time zone` | Không | — |
| `created_at` | `timestamp with time zone` | Không | `now()` |
| `updated_at` | `timestamp with time zone` | Không | `now()` |
| `version` | `bigint` | Không | `0` |
| `recipient_email` | `character varying(320)` | Có | — |
| `refund_reason` | `character varying(500)` | Có | — |
| `refund_requested_by_role` | `character varying(30)` | Có | — |
| `refund_requested_at` | `timestamp with time zone` | Có | — |
| `refunded_at` | `timestamp with time zone` | Có | — |
| `refund_reference` | `character varying(200)` | Có | — |
| `refund_requested_by_identity` | `uuid` | Có | — |
| `refund_initiator` | `character varying(30)` | Có | — |
| `refund_amount` | `numeric(12,0)` | Có | — |
| `refund_completed_by_identity` | `uuid` | Có | — |
| `refund_completed_by_role` | `character varying(30)` | Có | — |
| `refund_method` | `character varying(30)` | Có | — |
| `refund_receipt_number` | `character varying(100)` | Có | — |
| `refund_recipient_name` | `character varying(200)` | Có | — |
| `refund_evidence_content_type` | `character varying(50)` | Có | — |
| `refund_evidence_original_name` | `character varying(255)` | Có | — |
| `refund_evidence_size_bytes` | `bigint` | Có | — |
| `refund_evidence_data` | `bytea` | Có | — |

Ràng buộc:

- **CHECK** `ck_payments_refund_method`: `CHECK (refund_method IS NULL OR (refund_method::text = ANY (ARRAY['BANK_TRANSFER'::character varying, 'CASH'::character varying]::text[])))`
- **CHECK** `payments_amount_check`: `CHECK (amount > 0::numeric)`
- **PK** `payments_pkey`: `PRIMARY KEY (id)`
- **UNIQUE** `payments_booking_id_key`: `UNIQUE (booking_id)`
- **UNIQUE** `payments_order_code_key`: `UNIQUE (order_code)`
- **UNIQUE** `payments_payment_link_id_key`: `UNIQUE (payment_link_id)`
- **UNIQUE** `payments_payos_trans_id_key`: `UNIQUE (payos_trans_id)`

Chỉ mục bổ sung:

- `ix_payments_expiry`: `CREATE INDEX ix_payments_expiry ON payment.payments USING btree (expires_at) WHERE ((status)::text = 'PENDING'::text)`
- `ix_payments_refund_requested`: `CREATE INDEX ix_payments_refund_requested ON payment.payments USING btree (updated_at) WHERE ((status)::text = 'REFUND_REQUESTED'::text)`
- `ux_payments_refund_receipt_number`: `CREATE UNIQUE INDEX ux_payments_refund_receipt_number ON payment.payments USING btree (refund_receipt_number) WHERE (refund_receipt_number IS NOT NULL)`

### `medical_record`

#### `medical_record.medical_records`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `appointment_id` | `uuid` | Không | — |
| `patient_id` | `uuid` | Không | — |
| `patient_identity_id` | `uuid` | Không | — |
| `doctor_id` | `uuid` | Không | — |
| `final_diagnosis` | `character varying(2000)` | Không | — |
| `clinical_notes` | `character varying(10000)` | Có | — |
| `treatment_plan` | `character varying(5000)` | Có | — |
| `severity` | `character varying(20)` | Không | — |
| `follow_up_at` | `timestamp with time zone` | Có | — |
| `signed_at` | `timestamp with time zone` | Không | — |
| `version` | `bigint` | Không | `0` |

Ràng buộc:

- **PK** `medical_records_pkey`: `PRIMARY KEY (id)`
- **UNIQUE** `medical_records_appointment_id_key`: `UNIQUE (appointment_id)`

Chỉ mục bổ sung:

- `ix_record_patient`: `CREATE INDEX ix_record_patient ON medical_record.medical_records USING btree (patient_id, signed_at DESC)`
- `ix_record_patient_identity`: `CREATE INDEX ix_record_patient_identity ON medical_record.medical_records USING btree (patient_identity_id, signed_at DESC)`

#### `medical_record.patient_record_visibility`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `record_id` | `uuid` | Không | — |
| `patient_identity_id` | `uuid` | Không | — |
| `hidden_at` | `timestamp with time zone` | Không | `CURRENT_TIMESTAMP` |

Ràng buộc:

- **FK** `patient_record_visibility_record_id_fkey`: `FOREIGN KEY (record_id) REFERENCES medical_record.medical_records(id)`
- **PK** `patient_record_visibility_pkey`: `PRIMARY KEY (record_id)`

Chỉ mục bổ sung:

- `ix_patient_record_visibility_patient`: `CREATE INDEX ix_patient_record_visibility_patient ON medical_record.patient_record_visibility USING btree (patient_identity_id, hidden_at DESC)`

### `prescription`

#### `prescription.inventory_movements`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `invoice_id` | `uuid` | Không | — |
| `medicine_id` | `uuid` | Không | — |
| `quantity_delta` | `integer` | Không | — |
| `performed_by` | `uuid` | Không | — |
| `created_at` | `timestamp with time zone` | Không | — |
| `reason` | `character varying(40)` | Không | — |

Ràng buộc:

- **FK** `inventory_movements_invoice_id_fkey`: `FOREIGN KEY (invoice_id) REFERENCES prescription.invoices(id) ON DELETE RESTRICT`
- **PK** `inventory_movements_pkey`: `PRIMARY KEY (id)`

Chỉ mục bổ sung:

- `uq_inventory_invoice_medicine`: `CREATE UNIQUE INDEX uq_inventory_invoice_medicine ON prescription.inventory_movements USING btree (invoice_id, medicine_id)`

#### `prescription.invoice_adjustments`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `invoice_id` | `uuid` | Không | — |
| `amount_delta` | `numeric(12,0)` | Không | — |
| `reason` | `character varying(500)` | Không | — |
| `created_by` | `uuid` | Không | — |
| `created_at` | `timestamp with time zone` | Không | — |

Ràng buộc:

- **FK** `invoice_adjustments_invoice_id_fkey`: `FOREIGN KEY (invoice_id) REFERENCES prescription.invoices(id) ON DELETE RESTRICT`
- **PK** `invoice_adjustments_pkey`: `PRIMARY KEY (id)`

#### `prescription.invoice_cash_payments`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `invoice_id` | `uuid` | Không | — |
| `amount_due` | `numeric(12,0)` | Không | — |
| `amount_received` | `numeric(12,0)` | Không | — |
| `change_amount` | `numeric(12,0)` | Không | — |
| `collected_by` | `uuid` | Không | — |
| `collected_at` | `timestamp with time zone` | Không | — |
| `cashier_station` | `character varying(120)` | Không | — |

Ràng buộc:

- **FK** `invoice_cash_payments_invoice_id_fkey`: `FOREIGN KEY (invoice_id) REFERENCES prescription.invoices(id) ON DELETE RESTRICT`
- **PK** `invoice_cash_payments_pkey`: `PRIMARY KEY (id)`
- **UNIQUE** `invoice_cash_payments_invoice_id_key`: `UNIQUE (invoice_id)`

#### `prescription.invoice_items`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `invoice_id` | `uuid` | Không | — |
| `medicine_id` | `uuid` | Không | — |
| `medicine_name` | `character varying(200)` | Không | — |
| `unit` | `character varying(40)` | Không | — |
| `unit_price` | `numeric(12,0)` | Không | — |
| `prescribed_quantity` | `integer` | Không | — |
| `dispensed_quantity` | `integer` | Không | `0` |
| `line_total` | `numeric(12,0)` | Không | — |

Ràng buộc:

- **FK** `invoice_items_invoice_id_fkey`: `FOREIGN KEY (invoice_id) REFERENCES prescription.invoices(id) ON DELETE RESTRICT`

#### `prescription.invoice_service_items`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `invoice_id` | `uuid` | Không | — |
| `service_id` | `uuid` | Không | — |
| `service_code` | `character varying(80)` | Không | — |
| `service_name` | `character varying(160)` | Không | — |
| `unit_price` | `numeric(12,0)` | Không | — |

Ràng buộc:

- **FK** `invoice_service_items_invoice_id_fkey`: `FOREIGN KEY (invoice_id) REFERENCES prescription.invoices(id) ON DELETE RESTRICT`

Chỉ mục bổ sung:

- `uq_invoice_service`: `CREATE UNIQUE INDEX uq_invoice_service ON prescription.invoice_service_items USING btree (invoice_id, service_id)`

#### `prescription.invoices`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `appointment_id` | `uuid` | Không | — |
| `patient_id` | `uuid` | Không | — |
| `patient_identity_id` | `uuid` | Không | — |
| `prescription_id` | `uuid` | Có | — |
| `consultation_fee` | `numeric(12,0)` | Không | — |
| `service_fee` | `numeric(12,0)` | Không | `0` |
| `medicine_total` | `numeric(12,0)` | Không | `0` |
| `deposit_applied` | `numeric(12,0)` | Không | `0` |
| `total_amount` | `numeric(12,0)` | Không | — |
| `remaining_amount` | `numeric(12,0)` | Không | — |
| `status` | `character varying(30)` | Không | — |
| `created_by` | `uuid` | Không | — |
| `created_at` | `timestamp with time zone` | Không | — |
| `paid_at` | `timestamp with time zone` | Có | — |
| `dispensed_at` | `timestamp with time zone` | Có | — |
| `dispensed_by` | `uuid` | Có | — |
| `version` | `bigint` | Không | `0` |
| `medicine_fulfillment` | `character varying(30)` | Không | — |

Ràng buộc:

- **CHECK** `ck_invoice_medicine_fulfillment`: `CHECK (medicine_fulfillment::text = ANY (ARRAY['CLINIC_PHARMACY'::character varying, 'OUTSIDE_PHARMACY'::character varying, 'NO_PRESCRIPTION'::character varying]::text[]))`
- **PK** `invoices_pkey`: `PRIMARY KEY (id)`
- **UNIQUE** `invoices_appointment_id_key`: `UNIQUE (appointment_id)`

Chỉ mục bổ sung:

- `idx_invoices_patient_identity`: `CREATE INDEX idx_invoices_patient_identity ON prescription.invoices USING btree (patient_identity_id, created_at DESC)`

#### `prescription.medicines`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `sku` | `character varying(60)` | Không | — |
| `name` | `character varying(200)` | Không | — |
| `unit` | `character varying(40)` | Không | — |
| `sale_price` | `numeric(12,0)` | Không | — |
| `stock_quantity` | `integer` | Không | `0` |
| `active` | `boolean` | Không | `true` |
| `updated_at` | `timestamp with time zone` | Không | `CURRENT_TIMESTAMP` |
| `version` | `bigint` | Không | `0` |

Ràng buộc:

- **CHECK** `medicines_sale_price_check`: `CHECK (sale_price >= 0::numeric)`
- **CHECK** `medicines_stock_quantity_check`: `CHECK (stock_quantity >= 0)`
- **PK** `medicines_pkey`: `PRIMARY KEY (id)`
- **UNIQUE** `medicines_sku_key`: `UNIQUE (sku)`

#### `prescription.prescription_items`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `prescription_id` | `uuid` | Không | — |
| `drug_name` | `character varying(200)` | Không | — |
| `dosage` | `character varying(120)` | Không | — |
| `frequency` | `character varying(120)` | Có | — |
| `duration` | `character varying(120)` | Có | — |
| `item_instructions` | `character varying(1000)` | Có | — |
| `medicine_id` | `uuid` | Có | — |
| `quantity_requested` | `integer` | Không | `1` |

Ràng buộc:

- **FK** `prescription_items_prescription_id_fkey`: `FOREIGN KEY (prescription_id) REFERENCES prescription.prescriptions(id) ON DELETE CASCADE`

#### `prescription.prescriptions`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `record_id` | `uuid` | Không | — |
| `patient_id` | `uuid` | Không | — |
| `patient_identity_id` | `uuid` | Không | — |
| `doctor_id` | `uuid` | Không | — |
| `instructions` | `character varying(3000)` | Có | — |
| `signed_at` | `timestamp with time zone` | Không | — |
| `appointment_id` | `uuid` | Có | — |

Ràng buộc:

- **PK** `prescriptions_pkey`: `PRIMARY KEY (id)`

Chỉ mục bổ sung:

- `ix_prescription_patient`: `CREATE INDEX ix_prescription_patient ON prescription.prescriptions USING btree (patient_id, signed_at DESC)`
- `ix_prescription_patient_identity`: `CREATE INDEX ix_prescription_patient_identity ON prescription.prescriptions USING btree (patient_identity_id, signed_at DESC)`
- `uq_prescription_record`: `CREATE UNIQUE INDEX uq_prescription_record ON prescription.prescriptions USING btree (record_id)`

### `pharmacy`

#### `pharmacy.inventory_logs`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `product_id` | `uuid` | Không | — |
| `batch_id` | `uuid` | Không | — |
| `action_type` | `character varying(20)` | Không | — |
| `quantity_changed` | `integer` | Không | — |
| `created_at` | `timestamp with time zone` | Không | — |

Ràng buộc:

- **CHECK** `ck_inventory_logs_action_type`: `CHECK (action_type::text = ANY (ARRAY['IMPORT'::character varying, 'DISPENSE'::character varying]::text[]))`
- **FK** `inventory_logs_batch_id_fkey`: `FOREIGN KEY (batch_id) REFERENCES pharmacy.product_batches(id) ON DELETE RESTRICT`
- **FK** `inventory_logs_product_id_fkey`: `FOREIGN KEY (product_id) REFERENCES pharmacy.products(id) ON DELETE RESTRICT`
- **PK** `inventory_logs_pkey`: `PRIMARY KEY (id)`

Chỉ mục bổ sung:

- `ix_inventory_logs_product_created`: `CREATE INDEX ix_inventory_logs_product_created ON pharmacy.inventory_logs USING btree (product_id, created_at)`

#### `pharmacy.prescription_items`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `prescription_id` | `uuid` | Không | — |
| `product_id` | `uuid` | Không | — |
| `batch_id` | `uuid` | Có | — |
| `quantity` | `integer` | Không | — |

Ràng buộc:

- **CHECK** `ck_prescription_items_quantity`: `CHECK (quantity > 0)`
- **FK** `prescription_items_batch_id_fkey`: `FOREIGN KEY (batch_id) REFERENCES pharmacy.product_batches(id) ON DELETE RESTRICT`
- **FK** `prescription_items_prescription_id_fkey`: `FOREIGN KEY (prescription_id) REFERENCES pharmacy.prescriptions(id) ON DELETE CASCADE`
- **FK** `prescription_items_product_id_fkey`: `FOREIGN KEY (product_id) REFERENCES pharmacy.products(id) ON DELETE RESTRICT`
- **PK** `prescription_items_pkey`: `PRIMARY KEY (id)`

Chỉ mục bổ sung:

- `ix_pharmacy_prescription_items_prescription_id`: `CREATE INDEX ix_pharmacy_prescription_items_prescription_id ON pharmacy.prescription_items USING btree (prescription_id)`

#### `pharmacy.prescriptions`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `patient_id` | `uuid` | Không | — |
| `patient_name` | `character varying(200)` | Không | — |
| `doctor_id` | `uuid` | Không | — |
| `status` | `character varying(30)` | Không | — |
| `paid_at` | `timestamp with time zone` | Có | — |
| `dispensed_at` | `timestamp with time zone` | Có | — |
| `dispensed_by` | `uuid` | Có | — |

Ràng buộc:

- **CHECK** `ck_pharmacy_prescriptions_status`: `CHECK (status::text = ANY (ARRAY['PENDING_PAYMENT'::character varying, 'PAID'::character varying, 'DISPENSED'::character varying, 'CANCELLED'::character varying]::text[]))`
- **PK** `prescriptions_pkey`: `PRIMARY KEY (id)`

Chỉ mục bổ sung:

- `ix_pharmacy_prescriptions_patient_id`: `CREATE INDEX ix_pharmacy_prescriptions_patient_id ON pharmacy.prescriptions USING btree (patient_id)`
- `ix_prescriptions_status_paid_at`: `CREATE INDEX ix_prescriptions_status_paid_at ON pharmacy.prescriptions USING btree (status, paid_at)`

#### `pharmacy.product_batches`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `product_id` | `uuid` | Không | — |
| `batch_number` | `character varying(100)` | Không | — |
| `expiry_date` | `date` | Không | — |
| `quantity` | `integer` | Không | — |

Ràng buộc:

- **CHECK** `ck_product_batches_quantity`: `CHECK (quantity >= 0)`
- **FK** `product_batches_product_id_fkey`: `FOREIGN KEY (product_id) REFERENCES pharmacy.products(id) ON DELETE RESTRICT`
- **PK** `product_batches_pkey`: `PRIMARY KEY (id)`
- **UNIQUE** `uq_product_batch_number`: `UNIQUE (product_id, batch_number)`

Chỉ mục bổ sung:

- `ix_pharmacy_product_batches_product_id`: `CREATE INDEX ix_pharmacy_product_batches_product_id ON pharmacy.product_batches USING btree (product_id)`
- `ix_product_batches_fefo`: `CREATE INDEX ix_product_batches_fefo ON pharmacy.product_batches USING btree (product_id, expiry_date)`

#### `pharmacy.products`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `sku` | `character varying(60)` | Không | — |
| `name` | `character varying(200)` | Không | — |
| `unit` | `character varying(40)` | Không | — |
| `import_price` | `numeric(12,0)` | Không | — |
| `selling_price` | `numeric(12,0)` | Không | — |
| `min_threshold` | `integer` | Không | — |
| `active` | `boolean` | Không | `true` |

Ràng buộc:

- **CHECK** `ck_products_import_price`: `CHECK (import_price >= 0::numeric)`
- **CHECK** `ck_products_min_threshold`: `CHECK (min_threshold >= 0)`
- **CHECK** `ck_products_selling_price`: `CHECK (selling_price >= 0::numeric)`
- **PK** `products_pkey`: `PRIMARY KEY (id)`
- **UNIQUE** `products_sku_key`: `UNIQUE (sku)`

### `notification`

#### `notification.deliveries`

| Cột | Kiểu | Null | Mặc định |
|---|---|---|---|
| `id` | `uuid` | Không | — |
| `event_id` | `uuid` | Không | — |
| `event_type` | `character varying(120)` | Không | — |
| `recipient` | `character varying(320)` | Không | — |
| `subject` | `character varying(300)` | Không | — |
| `created_at` | `timestamp with time zone` | Không | `now()` |
| `sent_at` | `timestamp with time zone` | Có | — |
| `last_error` | `character varying(2000)` | Có | — |
| `attempts` | `integer` | Không | `0` |

Ràng buộc:

- **PK** `deliveries_pkey`: `PRIMARY KEY (id)`
- **UNIQUE** `deliveries_event_id_key`: `UNIQUE (event_id)`

Chỉ mục bổ sung:

- `ix_delivery_unsent`: `CREATE INDEX ix_delivery_unsent ON notification.deliveries USING btree (created_at) WHERE (sent_at IS NULL)`

## Liên kết giữa service

Bảng ánh xạ và cardinality để vẽ ERD toàn hệ thống nằm trong
[`database-erd-guide.md`](database-erd-guide.md).

Mỗi service sở hữu schema riêng. Các UUID liên kết xuyên schema được kiểm tra ở tầng ứng dụng;
chúng không phải FK vật lý của PostgreSQL. Ví dụ: `appointment.appointments.patient_id`
tham chiếu logic đến `patient.patients.id`, `appointment.appointments.doctor_id` đến
`doctor.doctors.id`, và `prescription.prescriptions.record_id` đến
`medical_record.medical_records.id`. Các ràng buộc FK vật lý được liệt kê tại từng bảng ở trên.

## Lưu ý sử dụng

File SQL tổng hợp dành cho database mới và rỗng; không chạy chồng lên database đã được Flyway
migrate. Trong môi trường Compose thông thường, các Java service tự chạy Flyway lúc khởi động;
`inventory-service` tạo bảng `pharmacy` từ SQLAlchemy model và có migration SQL tham chiếu riêng.
