ALTER TABLE appointments ADD COLUMN IF NOT EXISTS patient_identity_id uuid;
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS doctor_identity_id uuid;
CREATE INDEX IF NOT EXISTS ix_appointment_patient_identity ON appointments(patient_identity_id,start_at DESC);
CREATE INDEX IF NOT EXISTS ix_appointment_doctor_identity ON appointments(doctor_identity_id,start_at) WHERE status<>'CANCELLED';

-- Không tự suy diễn identity cho dữ liệu cũ. Các bản ghi legacy thiếu identity
-- phải được đối soát bằng Auth/Patient/Doctor service trước khi gán thủ công.
