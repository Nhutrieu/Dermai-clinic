ALTER TABLE payments
  ADD COLUMN refund_method varchar(30),
  ADD COLUMN refund_receipt_number varchar(100),
  ADD COLUMN refund_recipient_name varchar(200),
  ADD COLUMN refund_evidence_content_type varchar(50),
  ADD COLUMN refund_evidence_original_name varchar(255),
  ADD COLUMN refund_evidence_size_bytes bigint,
  ADD COLUMN refund_evidence_data bytea;

CREATE UNIQUE INDEX ux_payments_refund_receipt_number
  ON payments(refund_receipt_number)
  WHERE refund_receipt_number IS NOT NULL;

ALTER TABLE payments
  ADD CONSTRAINT ck_payments_refund_method
  CHECK (refund_method IS NULL OR refund_method IN ('BANK_TRANSFER', 'CASH'));