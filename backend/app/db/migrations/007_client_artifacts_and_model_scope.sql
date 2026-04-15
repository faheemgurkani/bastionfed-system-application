-- Client training artifacts (images / JSON) in a single bucket with tenant/client/label paths
CREATE TABLE IF NOT EXISTS client_artifacts (
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    id TEXT NOT NULL,
    fl_client_id TEXT NOT NULL,
    label TEXT NOT NULL CHECK (label IN ('benign', 'malware')),
    kind TEXT NOT NULL DEFAULT 'other',
    filename TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    storage_bucket TEXT NOT NULL,
    storage_object_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'UPLOADED',
    notes TEXT,
    uploaded_by_uid TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, id),
    FOREIGN KEY (tenant_id, fl_client_id) REFERENCES fl_clients(tenant_id, id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_client_artifacts_tenant_client ON client_artifacts(tenant_id, fl_client_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_client_artifacts_label ON client_artifacts(tenant_id, label);

-- Model registry: optional client binding + storage path + scope (tenant-wide vs client-only)
ALTER TABLE model_registry
    ADD COLUMN IF NOT EXISTS fl_client_id TEXT,
    ADD COLUMN IF NOT EXISTS storage_path TEXT,
    ADD COLUMN IF NOT EXISTS model_scope TEXT NOT NULL DEFAULT 'tenant';

UPDATE model_registry SET model_scope = 'tenant' WHERE model_scope IS NULL OR model_scope = '';

-- Per FL client active model (inference selection)
CREATE TABLE IF NOT EXISTS fl_client_active_models (
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    fl_client_id TEXT NOT NULL,
    model_name TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_by_uid TEXT NOT NULL,
    PRIMARY KEY (tenant_id, fl_client_id),
    FOREIGN KEY (tenant_id, fl_client_id) REFERENCES fl_clients(tenant_id, id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, model_name) REFERENCES model_registry(tenant_id, name) ON DELETE CASCADE
);
