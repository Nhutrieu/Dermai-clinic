# Hướng dẫn vẽ ERD DermAI Clinic

Nguồn bảng, 417 cột, PK, FK, UNIQUE, CHECK và chỉ mục là
[`database-schema-reference.md`](database-schema-reference.md). ERD nghiệp vụ gồm 48 bảng trong
9 schema; bỏ các bảng `flyway_schema_history`. File
[`dermai_full_schema.sql`](../database/dermai_full_schema.sql) là nguồn SQL cho database mới.

## Quy ước đường nối

- **Nét liền:** FK vật lý ghi trong mục “Ràng buộc” của từng bảng trong tài liệu schema.
  Đích của `REFERENCES` là bảng cha. Cột `UNIQUE` hoặc PK ở phía con giới hạn quan hệ
  thành tối đa một bản ghi con; nếu không có thì là nhiều. Cột nullable cho phép không có cha.
- **Nét đứt, nhãn `REF`:** UUID có ý nghĩa liên kết nhưng không có FK PostgreSQL.
  Các service kiểm tra tính hợp lệ qua API hoặc đồng bộ dữ liệu. Cardinality dưới đây là
  quy tắc nghiệp vụ hoặc giới hạn `UNIQUE` hiện có; PostgreSQL không cưỡng chế tồn tại cha.
- **Không vẽ FK giả** cho ID sự kiện đa hình, người thao tác hoặc các ảnh chụp giá/tên.
  Các trường này được chú thích riêng dưới đây.

## Liên kết logic giữa schema

Mỗi dòng `A → B` nghĩa là cột bên trái tham chiếu `B.id`, trừ khi đích ghi cột khác.
`1 → 0..1` nghĩa là một bản ghi đích có tối đa một bản ghi nguồn; `1 → 0..n` nghĩa là
có thể có nhiều. Các cột nullable được đánh dấu `?`.

| Cột nguồn | Đích | Bội số từ đích đến nguồn |
|---|---|---|
| `patient.patients.identity_id` | `auth.identities.id` | 1 → 0..1 (`UNIQUE`) |
| `doctor.doctors.identity_id` ? | `auth.identities.id` | 1 → 0..1 (`UNIQUE`) |
| `patient.ai_assessments.patient_identity_id` | `auth.identities.id` | 1 → 0..n |
| `patient.ai_assessments.appointment_id` ? | `appointment.appointments.id` | 1 → 0..n |
| `patient.ai_consent_events.patient_identity_id` | `auth.identities.id` | 1 → 0..n |
| `patient.ai_access_audit_logs.patient_identity_id` ? | `auth.identities.id` | 1 → 0..n |
| `patient.ai_access_audit_logs.actor_identity_id` | `auth.identities.id` | 1 → 0..n |
| `doctor.leave_approval_views.receptionist_identity_id` | `auth.identities.id` | 1 → 0..n |
| `appointment.appointments.patient_id` | `patient.patients.id` | 1 → 0..n |
| `appointment.appointments.patient_identity_id` | `auth.identities.id` | 1 → 0..n |
| `appointment.appointments.doctor_id` ? | `doctor.doctors.id` | 1 → 0..n |
| `appointment.appointments.doctor_identity_id` ? | `auth.identities.id` | 1 → 0..n |
| `appointment.appointment_performed_services.service_id` | `doctor.clinic_services.id` | 1 → 0..n |
| `payment.payments.booking_id` | `appointment.appointments.id` | 1 → 0..1 (`UNIQUE`) |
| `payment.payments.patient_identity_id` | `auth.identities.id` | 1 → 0..n |
| `payment.invoice_payments.invoice_id` | `prescription.invoices.id` | 1 → 0..1 (`UNIQUE`) |
| `payment.invoice_payments.patient_identity_id` | `auth.identities.id` | 1 → 0..n |
| `medical_record.medical_records.appointment_id` | `appointment.appointments.id` | 1 → 0..1 (`UNIQUE`) |
| `medical_record.medical_records.patient_id` | `patient.patients.id` | 1 → 0..n |
| `medical_record.medical_records.patient_identity_id` | `auth.identities.id` | 1 → 0..n |
| `medical_record.medical_records.doctor_id` | `doctor.doctors.id` | 1 → 0..n |
| `medical_record.patient_record_visibility.patient_identity_id` | `auth.identities.id` | 1 → 0..n |
| `prescription.prescriptions.record_id` | `medical_record.medical_records.id` | 1 → 0..1 (`UNIQUE`) |
| `prescription.prescriptions.appointment_id` ? | `appointment.appointments.id` | 1 → 0..n theo DB |
| `prescription.prescriptions.patient_id` | `patient.patients.id` | 1 → 0..n |
| `prescription.prescriptions.patient_identity_id` | `auth.identities.id` | 1 → 0..n |
| `prescription.prescriptions.doctor_id` | `doctor.doctors.id` | 1 → 0..n |
| `prescription.invoices.appointment_id` | `appointment.appointments.id` | 1 → 0..1 (`UNIQUE`) |
| `prescription.invoices.patient_id` | `patient.patients.id` | 1 → 0..n |
| `prescription.invoices.patient_identity_id` | `auth.identities.id` | 1 → 0..n |
| `prescription.invoice_service_items.service_id` | `doctor.clinic_services.id` | 1 → 0..n |
| `pharmacy.prescriptions.patient_id` | `patient.patients.id` | 1 → 0..n |
| `pharmacy.prescriptions.doctor_id` | `doctor.doctors.id` | 1 → 0..n |
| `notification.deliveries.event_id` | `appointment.outbox_events.id` | 1 → 0..1 (`UNIQUE`) |

Hai cặp đồng bộ dùng **cùng UUID**, không phải FK vật lý:

| Bản ghi đồng bộ | Bản ghi nguồn | Bội số |
|---|---|---|
| `pharmacy.products.id` | `prescription.medicines.id` | 1 → 0..1 |
| `pharmacy.prescriptions.id` | `prescription.invoices.id` | 1 → 0..1 |

## Liên kết logic trong cùng schema

Các liên kết sau không có FK vật lý, nên cũng dùng nét đứt nếu cần thể hiện:

| Cột nguồn | Đích | Ghi chú |
|---|---|---|
| `patient.ai_access_audit_logs.assessment_id` ? | `patient.ai_assessments.id` | Nhật ký có thể không gắn assessment. |
| `appointment.support_messages.patient_identity_id` | `appointment.support_conversations.patient_identity_id` | Một cuộc trò chuyện có nhiều tin nhắn. |
| `prescription.invoices.prescription_id` ? | `prescription.prescriptions.id` | Hóa đơn có thể không kèm đơn thuốc. |
| `prescription.prescription_items.medicine_id` ? | `prescription.medicines.id` | Thuốc danh mục; tên thuốc vẫn được lưu riêng. |
| `prescription.invoice_items.medicine_id` | `prescription.medicines.id` | Dòng hóa đơn lưu giá/tên tại thời điểm lập. |
| `prescription.inventory_movements.medicine_id` | `prescription.medicines.id` | Biến động của thuốc danh mục. |

## ID ngữ cảnh và người thao tác

- Các cột `*_identity_id` còn lại trong `appointment`, `patient`, `doctor`, `payment`,
  `medical_record` và `prescription` trỏ logic đến `auth.identities.id` khi biểu diễn
  người gửi, người phụ trách, bệnh nhân hoặc nhân viên. Các cột `created_by`,
  `confirmed_by`, `services_confirmed_by`, `collected_by`, `performed_by`,
  `dispensed_by`, `requested_by`, `reviewed_by` và `refund_requested_by_identity`
  là UUID người thao tác. Chúng
  không có FK xuyên service; có thể ghi nhãn `actor REF` để tránh quá nhiều đường nối.
- `appointment.outbox_events.aggregate_id` thường là ID lịch khám theo loại sự kiện.
  `payment.payment_outbox_events.aggregate_id` là ID của `payment.payments` hoặc
  `payment.invoice_payments` theo `routing_key`. Đây là tham chiếu đa hình, không nối
  cứng vào một bảng trong ERD vật lý.
- `prescription.invoice_items`, `prescription.invoice_service_items` và
  `prescription.prescription_items` không có PK riêng trong schema hiện tại. Thể hiện
  chúng là bảng chi tiết phụ thuộc bảng cha; không tự thêm PK vào sơ đồ.

Các giới hạn vận hành như không trùng lịch bác sĩ/bệnh nhân nằm ở CHECK, UNIQUE và
EXCLUDE trong tài liệu schema. Chúng nên được ghi chú cạnh `appointment.appointments`,
không thể diễn đạt chỉ bằng đường nối ERD.
