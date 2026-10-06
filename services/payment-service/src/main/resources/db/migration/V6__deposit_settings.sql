CREATE TABLE deposit_settings (
  id integer PRIMARY KEY CHECK (id = 1),
  amount numeric(12,0) NOT NULL CHECK (amount BETWEEN 1000 AND 100000000),
  updated_at timestamptz NOT NULL DEFAULT now(),
  updated_by uuid
);
