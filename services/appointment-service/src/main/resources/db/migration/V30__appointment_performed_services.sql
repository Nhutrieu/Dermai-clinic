ALTER TABLE appointments ADD COLUMN services_confirmed_at TIMESTAMPTZ;
ALTER TABLE appointments ADD COLUMN services_confirmed_by UUID;

-- Existing finished visits predate service confirmation. Treat them as confirmed
-- with no additional services so they remain billable after this migration.
UPDATE appointments
SET services_confirmed_at = COALESCE(updated_at, created_at, now()),
    services_confirmed_by = doctor_identity_id
WHERE status IN ('COMPLETED', 'FOLLOW_UP_REQUIRED');

CREATE TABLE appointment_performed_services (
    id UUID PRIMARY KEY,
    appointment_id UUID NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
    service_id UUID NOT NULL,
    service_code VARCHAR(80) NOT NULL,
    service_name VARCHAR(160) NOT NULL,
    unit_price NUMERIC(12, 0) NOT NULL CHECK (unit_price >= 0),
    confirmed_by UUID NOT NULL,
    confirmed_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_appointment_performed_service UNIQUE (appointment_id, service_id)
);

CREATE INDEX ix_appointment_performed_services_appointment
    ON appointment_performed_services (appointment_id);
