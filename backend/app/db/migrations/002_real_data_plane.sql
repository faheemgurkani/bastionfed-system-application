ALTER TABLE devices
    ADD COLUMN IF NOT EXISTS source_type TEXT,
    ADD COLUMN IF NOT EXISTS source_ref TEXT,
    ADD COLUMN IF NOT EXISTS ingested_at TEXT,
    ADD COLUMN IF NOT EXISTS is_demo BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE alerts
    ADD COLUMN IF NOT EXISTS source_type TEXT,
    ADD COLUMN IF NOT EXISTS source_ref TEXT,
    ADD COLUMN IF NOT EXISTS ingested_at TEXT,
    ADD COLUMN IF NOT EXISTS is_demo BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE incidents
    ADD COLUMN IF NOT EXISTS source_type TEXT,
    ADD COLUMN IF NOT EXISTS source_ref TEXT,
    ADD COLUMN IF NOT EXISTS ingested_at TEXT,
    ADD COLUMN IF NOT EXISTS is_demo BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE malware_samples
    ADD COLUMN IF NOT EXISTS scan_status TEXT NOT NULL DEFAULT 'NOT_SCANNED',
    ADD COLUMN IF NOT EXISTS quarantine_status TEXT NOT NULL DEFAULT 'NONE',
    ADD COLUMN IF NOT EXISTS retention_status TEXT NOT NULL DEFAULT 'ACTIVE',
    ADD COLUMN IF NOT EXISTS chain_of_custody_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS scanner_verdict_json JSONB,
    ADD COLUMN IF NOT EXISTS is_demo BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS ingest_sources (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    connector_kind TEXT NOT NULL,
    secret_hash TEXT NOT NULL,
    secret_last_rotated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ingest_sources_tenant ON ingest_sources(tenant_id, created_at DESC);

CREATE TABLE IF NOT EXISTS ingest_events (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    source_id TEXT NOT NULL REFERENCES ingest_sources(id) ON DELETE CASCADE,
    external_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json JSONB NOT NULL,
    parse_status TEXT NOT NULL,
    normalized_targets_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    received_at TEXT NOT NULL,
    occurred_at TEXT,
    created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ingest_events_dedupe ON ingest_events(tenant_id, source_id, external_id);
CREATE INDEX IF NOT EXISTS idx_ingest_events_tenant_received_at ON ingest_events(tenant_id, received_at DESC);
