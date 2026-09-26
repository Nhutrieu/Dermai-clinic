ALTER TABLE appointments
  ADD COLUMN payment_method varchar(30),
  ADD COLUMN payment_override_reason varchar(500);

UPDATE appointments
SET payment_method = 'ONLINE_DEPOSIT'
WHERE status = 'PENDING_PAYMENT';