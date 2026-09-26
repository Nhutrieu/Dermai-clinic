ALTER TABLE prescription.invoices
    ADD COLUMN IF NOT EXISTS medicine_fulfillment VARCHAR(30);

UPDATE prescription.invoices AS invoice
SET medicine_fulfillment = CASE
    WHEN invoice.prescription_id IS NULL THEN 'NO_PRESCRIPTION'
    WHEN EXISTS (
        SELECT 1
        FROM prescription.invoice_items AS item
        WHERE item.invoice_id = invoice.id
          AND item.prescribed_quantity > 0
    ) THEN 'CLINIC_PHARMACY'
    ELSE 'OUTSIDE_PHARMACY'
END
WHERE medicine_fulfillment IS NULL;

ALTER TABLE prescription.invoices
    ALTER COLUMN medicine_fulfillment SET NOT NULL;

ALTER TABLE prescription.invoices
    ADD CONSTRAINT ck_invoice_medicine_fulfillment
    CHECK (medicine_fulfillment IN ('CLINIC_PHARMACY', 'OUTSIDE_PHARMACY', 'NO_PRESCRIPTION'));