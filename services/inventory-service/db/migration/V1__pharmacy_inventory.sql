CREATE SCHEMA IF NOT EXISTS pharmacy;
SET search_path TO pharmacy, public;

CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY,
    sku VARCHAR(60) NOT NULL,
    name VARCHAR(200) NOT NULL,
    unit VARCHAR(40) NOT NULL,
    import_price NUMERIC(12, 0) NOT NULL,
    selling_price NUMERIC(12, 0) NOT NULL,
    min_threshold INTEGER NOT NULL DEFAULT 0,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_products_sku UNIQUE (sku),
    CONSTRAINT ck_products_import_price CHECK (import_price >= 0),
    CONSTRAINT ck_products_selling_price CHECK (selling_price >= 0),
    CONSTRAINT ck_products_min_threshold CHECK (min_threshold >= 0)
);

CREATE TABLE IF NOT EXISTS product_batches (
    id UUID PRIMARY KEY,
    product_id UUID NOT NULL REFERENCES pharmacy.products(id) ON DELETE RESTRICT,
    batch_number VARCHAR(100) NOT NULL,
    expiry_date DATE NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT uq_product_batch_number UNIQUE (product_id, batch_number),
    CONSTRAINT ck_product_batches_quantity CHECK (quantity >= 0)
);

CREATE INDEX IF NOT EXISTS ix_product_batches_product_id
    ON pharmacy.product_batches(product_id);
CREATE INDEX IF NOT EXISTS ix_product_batches_fefo
    ON pharmacy.product_batches(product_id, expiry_date);

CREATE TABLE IF NOT EXISTS prescriptions (
    id UUID PRIMARY KEY,
    patient_id UUID NOT NULL,
    patient_name VARCHAR(200) NOT NULL,
    doctor_id UUID NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'PENDING_PAYMENT',
    paid_at TIMESTAMPTZ,
    dispensed_at TIMESTAMPTZ,
    dispensed_by UUID,
    CONSTRAINT ck_pharmacy_prescriptions_status
        CHECK (status IN ('PENDING_PAYMENT', 'PAID', 'DISPENSED', 'CANCELLED'))
);

CREATE INDEX IF NOT EXISTS ix_prescriptions_patient_id
    ON pharmacy.prescriptions(patient_id);
CREATE INDEX IF NOT EXISTS ix_prescriptions_status_paid_at
    ON pharmacy.prescriptions(status, paid_at);

CREATE TABLE IF NOT EXISTS prescription_items (
    id UUID PRIMARY KEY,
    prescription_id UUID NOT NULL REFERENCES pharmacy.prescriptions(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES pharmacy.products(id) ON DELETE RESTRICT,
    batch_id UUID REFERENCES pharmacy.product_batches(id) ON DELETE RESTRICT,
    quantity INTEGER NOT NULL,
    CONSTRAINT ck_prescription_items_quantity CHECK (quantity > 0)
);

CREATE INDEX IF NOT EXISTS ix_prescription_items_prescription_id
    ON pharmacy.prescription_items(prescription_id);

CREATE TABLE IF NOT EXISTS inventory_logs (
    id UUID PRIMARY KEY,
    product_id UUID NOT NULL REFERENCES pharmacy.products(id) ON DELETE RESTRICT,
    batch_id UUID NOT NULL REFERENCES pharmacy.product_batches(id) ON DELETE RESTRICT,
    action_type VARCHAR(20) NOT NULL,
    quantity_changed INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_inventory_logs_action_type
        CHECK (action_type IN ('IMPORT', 'DISPENSE'))
);

CREATE INDEX IF NOT EXISTS ix_inventory_logs_product_created
    ON pharmacy.inventory_logs(product_id, created_at);

SET search_path TO public;
