CREATE TABLE leave_approval_views (
  id UUID PRIMARY KEY,
  leave_id UUID NOT NULL REFERENCES leave_periods(id) ON DELETE CASCADE,
  receptionist_identity_id UUID NOT NULL,
  viewed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_leave_approval_view UNIQUE (leave_id, receptionist_identity_id)
);

CREATE INDEX ix_leave_approval_view_receptionist
  ON leave_approval_views (receptionist_identity_id, viewed_at);