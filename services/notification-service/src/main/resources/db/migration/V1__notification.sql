CREATE TABLE deliveries(id uuid PRIMARY KEY,event_id uuid NOT NULL UNIQUE,event_type varchar(120) NOT NULL,recipient varchar(320) NOT NULL,subject varchar(300) NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),sent_at timestamptz,last_error varchar(2000),attempts int NOT NULL DEFAULT 0);
CREATE INDEX ix_delivery_unsent ON deliveries(created_at) WHERE sent_at IS NULL;
