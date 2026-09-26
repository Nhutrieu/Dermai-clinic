CREATE TABLE IF NOT EXISTS prescription.invoice_service_items (
 invoice_id UUID NOT NULL REFERENCES prescription.invoices(id) ON DELETE RESTRICT,
 service_id UUID NOT NULL, service_code VARCHAR(80) NOT NULL,
 service_name VARCHAR(160) NOT NULL, unit_price NUMERIC(12,0) NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_invoice_service ON prescription.invoice_service_items(invoice_id,service_id);