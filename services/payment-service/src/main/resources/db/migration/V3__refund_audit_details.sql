ALTER TABLE payments
  ADD COLUMN refund_requested_by_identity uuid,
  ADD COLUMN refund_initiator varchar(30),
  ADD COLUMN refund_amount numeric(12,0),
  ADD COLUMN refund_completed_by_identity uuid,
  ADD COLUMN refund_completed_by_role varchar(30);