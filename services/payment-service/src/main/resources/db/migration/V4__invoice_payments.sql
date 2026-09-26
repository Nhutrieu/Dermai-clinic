CREATE TABLE IF NOT EXISTS payment.invoice_payments (
 id UUID PRIMARY KEY, invoice_id UUID NOT NULL UNIQUE, patient_identity_id UUID NOT NULL,
 amount NUMERIC(12,0) NOT NULL CHECK (amount > 0), order_code BIGINT NOT NULL UNIQUE,
 status VARCHAR(30) NOT NULL, payos_trans_id VARCHAR(255) UNIQUE, payment_link_id VARCHAR(255) UNIQUE,
 checkout_url TEXT, qr_code TEXT, expires_at TIMESTAMPTZ NOT NULL,
 created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL, version BIGINT NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_invoice_payments_patient ON payment.invoice_payments(patient_identity_id,created_at DESC);