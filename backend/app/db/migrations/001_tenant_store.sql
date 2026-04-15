CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
    firebase_uid TEXT PRIMARY KEY,
    email TEXT,
    display_name TEXT,
    photo_url TEXT,
    created_at TEXT NOT NULL,
    last_login_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tenants (
    id TEXT PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS memberships (
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    firebase_uid TEXT NOT NULL REFERENCES users(firebase_uid) ON DELETE CASCADE,
    role TEXT NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, firebase_uid)
);
CREATE INDEX IF NOT EXISTS idx_memberships_user_default ON memberships(firebase_uid, is_default DESC, created_at ASC);

CREATE TABLE IF NOT EXISTS devices (
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    id TEXT NOT NULL,
    name TEXT NOT NULL,
    ip TEXT NOT NULL,
    type TEXT NOT NULL,
    wing TEXT NOT NULL,
    criticality INTEGER NOT NULL,
    fl_client_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, id)
);

CREATE TABLE IF NOT EXISTS alerts (
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    device_id TEXT NOT NULL,
    type TEXT NOT NULL,
    tactic TEXT NOT NULL,
    technique_json JSONB NOT NULL,
    severity TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    status TEXT NOT NULL,
    model_version TEXT NOT NULL,
    threat_intel_json JSONB NOT NULL,
    cve_reference TEXT,
    feature_summary TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, id)
);
CREATE INDEX IF NOT EXISTS idx_alerts_tenant_timestamp ON alerts(tenant_id, timestamp DESC);

CREATE TABLE IF NOT EXISTS incidents (
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    id TEXT NOT NULL,
    title TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    affected_device_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    time_open TEXT NOT NULL,
    analyst_initials TEXT NOT NULL,
    playbook_json JSONB NOT NULL,
    ticket_id TEXT NOT NULL,
    reporter TEXT NOT NULL,
    assignee TEXT NOT NULL,
    priority TEXT NOT NULL,
    created TEXT NOT NULL,
    labels_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, id)
);

CREATE TABLE IF NOT EXISTS incident_events (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    incident_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    type TEXT NOT NULL,
    description TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_incident_events_tenant_incident ON incident_events(tenant_id, incident_id, timestamp ASC);

CREATE TABLE IF NOT EXISTS fl_clients (
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    id TEXT NOT NULL,
    department TEXT NOT NULL,
    participation_pct DOUBLE PRECISION NOT NULL,
    last_round INTEGER NOT NULL,
    dp_epsilon DOUBLE PRECISION NOT NULL,
    model_version TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, id)
);

CREATE TABLE IF NOT EXISTS fl_rounds (
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    round INTEGER NOT NULL,
    session_id TEXT NOT NULL,
    accuracy DOUBLE PRECISION NOT NULL,
    fp_rate DOUBLE PRECISION NOT NULL,
    train_loss DOUBLE PRECISION NOT NULL,
    val_loss DOUBLE PRECISION NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, round)
);

CREATE TABLE IF NOT EXISTS model_registry (
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    model_type TEXT NOT NULL,
    accuracy DOUBLE PRECISION NOT NULL,
    fp_rate DOUBLE PRECISION NOT NULL,
    size TEXT NOT NULL,
    trained_on TEXT NOT NULL,
    description TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, name)
);

CREATE TABLE IF NOT EXISTS malware_samples (
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    id TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    md5 TEXT NOT NULL,
    filename TEXT NOT NULL,
    size TEXT NOT NULL,
    type TEXT NOT NULL,
    device_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    upload_time TEXT NOT NULL,
    family TEXT NOT NULL,
    threat_score INTEGER NOT NULL,
    status TEXT NOT NULL,
    analysis_json JSONB NOT NULL,
    storage_bucket TEXT,
    storage_object_key TEXT,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, id)
);

CREATE TABLE IF NOT EXISTS rca_reports (
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    id TEXT NOT NULL,
    incident_id TEXT NOT NULL,
    title TEXT NOT NULL,
    executive_summary TEXT NOT NULL,
    timeline_nodes_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    affected_nodes_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    mitre_chain_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    response_actions_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    recommendations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL,
    prev_hash TEXT NOT NULL,
    hash TEXT NOT NULL,
    actor_firebase_uid TEXT NOT NULL,
    actor_label TEXT NOT NULL,
    action TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    result TEXT NOT NULL,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, sequence)
);
CREATE INDEX IF NOT EXISTS idx_audit_log_tenant_created_at ON audit_log(tenant_id, created_at DESC);
