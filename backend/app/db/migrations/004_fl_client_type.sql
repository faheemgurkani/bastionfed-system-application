-- FL client classification: DEVICE (node scope) vs PERSON (human login + invites)

ALTER TABLE fl_clients
  ADD COLUMN IF NOT EXISTS client_type TEXT NOT NULL DEFAULT 'DEVICE';
