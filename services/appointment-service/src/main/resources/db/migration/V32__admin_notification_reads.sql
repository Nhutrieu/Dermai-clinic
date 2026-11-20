CREATE TABLE admin_notification_reads (
    admin_identity_id uuid NOT NULL,
    notification_key varchar(240) NOT NULL,
    read_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (admin_identity_id, notification_key)
);
CREATE INDEX ix_admin_notification_reads_recent ON admin_notification_reads(admin_identity_id, read_at DESC);
