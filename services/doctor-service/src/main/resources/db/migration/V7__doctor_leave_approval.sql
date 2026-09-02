ALTER TABLE leave_periods
  ADD COLUMN status varchar(20) NOT NULL DEFAULT 'APPROVED',
  ADD COLUMN requested_by uuid,
  ADD COLUMN reviewed_by uuid,
  ADD COLUMN reviewed_at timestamptz,
  ADD COLUMN review_note varchar(250);

ALTER TABLE leave_periods
  ADD CONSTRAINT ck_leave_period_status CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED'));

CREATE INDEX ix_leave_status_time ON leave_periods(status, start_at, end_at);