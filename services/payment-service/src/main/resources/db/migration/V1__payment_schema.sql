CREATE SEQUENCE payment_order_code_seq START WITH 1000000000 INCREMENT BY 1;

CREATE TABLE payments (
  id uuid PRIMARY KEY,
  booking_id uuid NOT NULL UNIQUE,
  patient_identity_id uuid NOT NULL,
  amount numeric(12,0) NOT NULL CHECK (amount > 0),
  order_code bigint NOT NULL UNIQUE,
  status varchar(30) NOT NULL,
  payos_trans_id varchar(100) UNIQUE,
  payment_link_id varchar(100) UNIQUE,
  checkout_url text,
  qr_code text,
  appointment_start_at timestamptz NOT NULL,
  expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  version bigint NOT NULL DEFAULT 0
);
CREATE INDEX ix_payments_expiry ON payments(expires_at) WHERE status = 'PENDING';

CREATE TABLE payment_outbox_events (
  id uuid PRIMARY KEY,
  aggregate_id uuid NOT NULL,
  routing_key varchar(100) NOT NULL,
  payload jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  published_at timestamptz,
  UNIQUE(aggregate_id, routing_key)
);
CREATE INDEX ix_payment_outbox_pending ON payment_outbox_events(created_at) WHERE published_at IS NULL;
