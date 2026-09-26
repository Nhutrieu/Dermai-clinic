ALTER TABLE prescription.prescriptions ADD COLUMN IF NOT EXISTS appointment_id UUID;
ALTER TABLE prescription.prescription_items ADD COLUMN IF NOT EXISTS medicine_id UUID;
ALTER TABLE prescription.prescription_items ADD COLUMN IF NOT EXISTS quantity_requested INTEGER NOT NULL DEFAULT 1;

CREATE TABLE IF NOT EXISTS prescription.medicines (
 id UUID PRIMARY KEY, sku VARCHAR(60) NOT NULL UNIQUE, name VARCHAR(200) NOT NULL,
 unit VARCHAR(40) NOT NULL, sale_price NUMERIC(12,0) NOT NULL CHECK (sale_price >= 0),
 stock_quantity INTEGER NOT NULL DEFAULT 0 CHECK (stock_quantity >= 0), active BOOLEAN NOT NULL DEFAULT TRUE,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, version BIGINT NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS prescription.invoices (
 id UUID PRIMARY KEY, appointment_id UUID NOT NULL UNIQUE, patient_id UUID NOT NULL, patient_identity_id UUID NOT NULL,
 prescription_id UUID, consultation_fee NUMERIC(12,0) NOT NULL, service_fee NUMERIC(12,0) NOT NULL DEFAULT 0,
 medicine_total NUMERIC(12,0) NOT NULL DEFAULT 0, deposit_applied NUMERIC(12,0) NOT NULL DEFAULT 0,
 total_amount NUMERIC(12,0) NOT NULL, remaining_amount NUMERIC(12,0) NOT NULL,
 status VARCHAR(30) NOT NULL, created_by UUID NOT NULL, created_at TIMESTAMPTZ NOT NULL,
 paid_at TIMESTAMPTZ, dispensed_at TIMESTAMPTZ, dispensed_by UUID, version BIGINT NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_invoices_patient_identity ON prescription.invoices(patient_identity_id,created_at DESC);
CREATE TABLE IF NOT EXISTS prescription.invoice_items (
 invoice_id UUID NOT NULL REFERENCES prescription.invoices(id) ON DELETE RESTRICT,
 medicine_id UUID NOT NULL, medicine_name VARCHAR(200) NOT NULL, unit VARCHAR(40) NOT NULL,
 unit_price NUMERIC(12,0) NOT NULL, prescribed_quantity INTEGER NOT NULL,
 dispensed_quantity INTEGER NOT NULL DEFAULT 0, line_total NUMERIC(12,0) NOT NULL
);
CREATE TABLE IF NOT EXISTS prescription.invoice_cash_payments (
 id UUID PRIMARY KEY, invoice_id UUID NOT NULL UNIQUE REFERENCES prescription.invoices(id) ON DELETE RESTRICT,
 amount_due NUMERIC(12,0) NOT NULL, amount_received NUMERIC(12,0) NOT NULL,
 change_amount NUMERIC(12,0) NOT NULL, collected_by UUID NOT NULL, collected_at TIMESTAMPTZ NOT NULL,
 cashier_station VARCHAR(120) NOT NULL
);
CREATE TABLE IF NOT EXISTS prescription.inventory_movements (
 id UUID PRIMARY KEY, invoice_id UUID NOT NULL REFERENCES prescription.invoices(id) ON DELETE RESTRICT,
 medicine_id UUID NOT NULL, quantity_delta INTEGER NOT NULL, performed_by UUID NOT NULL,
 created_at TIMESTAMPTZ NOT NULL, reason VARCHAR(40) NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_inventory_invoice_medicine ON prescription.inventory_movements(invoice_id,medicine_id);
CREATE TABLE IF NOT EXISTS prescription.invoice_adjustments (
 id UUID PRIMARY KEY, invoice_id UUID NOT NULL REFERENCES prescription.invoices(id) ON DELETE RESTRICT,
 amount_delta NUMERIC(12,0) NOT NULL, reason VARCHAR(500) NOT NULL,
 created_by UUID NOT NULL, created_at TIMESTAMPTZ NOT NULL
);