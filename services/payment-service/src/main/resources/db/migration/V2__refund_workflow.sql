ALTER TABLE payments
  ADD COLUMN recipient_email varchar(320),
  ADD COLUMN refund_reason varchar(500),
  ADD COLUMN refund_requested_by_role varchar(30),
  ADD COLUMN refund_requested_at timestamptz,
  ADD COLUMN refunded_at timestamptz,
  ADD COLUMN refund_reference varchar(200);

CREATE INDEX ix_payments_refund_requested
  ON payments(updated_at)
  WHERE status = 'REFUND_REQUESTED';