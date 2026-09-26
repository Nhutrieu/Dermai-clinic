ALTER TABLE support_messages
  ADD COLUMN attachment_content_type varchar(50),
  ADD COLUMN attachment_original_name varchar(255),
  ADD COLUMN attachment_size_bytes bigint,
  ADD COLUMN attachment_data bytea;