-- Track which admin provisioned each FL client (per-admin limits)
ALTER TABLE fl_clients
  ADD COLUMN IF NOT EXISTS created_by_firebase_uid TEXT;

CREATE INDEX IF NOT EXISTS idx_fl_clients_tenant_created_by
  ON fl_clients (tenant_id, created_by_firebase_uid);
