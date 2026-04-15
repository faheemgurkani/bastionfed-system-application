-- Per-client/site access scopes for client_user role and invite-based onboarding

CREATE TABLE IF NOT EXISTS membership_client_scopes (
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    firebase_uid TEXT NOT NULL REFERENCES users(firebase_uid) ON DELETE CASCADE,
    fl_client_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, firebase_uid, fl_client_id)
);
CREATE INDEX IF NOT EXISTS idx_membership_client_scopes_user ON membership_client_scopes(firebase_uid, tenant_id);

CREATE TABLE IF NOT EXISTS client_user_invites (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    invite_token TEXT NOT NULL UNIQUE,
    email TEXT,
    fl_client_ids TEXT[] NOT NULL DEFAULT '{}',
    expires_at TIMESTAMPTZ NOT NULL,
    created_by_firebase_uid TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    consumed_at TIMESTAMPTZ,
    consumed_by_firebase_uid TEXT
);
CREATE INDEX IF NOT EXISTS idx_client_user_invites_token ON client_user_invites(invite_token);
CREATE INDEX IF NOT EXISTS idx_client_user_invites_tenant ON client_user_invites(tenant_id);
