-- Creates the security table — a tenant's SSO / MFA and session & password
-- policy (the onboarding "Security" step).
--
-- The table is defined by app/security/models/security.py and is created
-- automatically in freshly provisioned tenant DBs (and at startup in the master
-- DB) via Base.metadata.create_all. This script provisions it for databases that
-- already exist. Run against:
--   1. The master DB (clan_platform)
--   2. EVERY existing tenant DB (clan_platform_<code>...)
--
-- Idempotent: CREATE TABLE / CREATE INDEX IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS security (
    security_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id                UUID REFERENCES tenants(tenant_id),

    -- Single sign-on (SSO)
    enable_sso               BOOLEAN NOT NULL DEFAULT false,

    -- Multi-factor authentication (MFA)
    require_mfa              BOOLEAN NOT NULL DEFAULT false,

    -- Session & password policy
    session_timeout_min      INTEGER,
    idle_timeout_min         INTEGER,
    max_concurrent_sessions  INTEGER,
    remember_me_days         INTEGER,
    password_min_length      INTEGER,
    password_expiry_days     INTEGER,
    password_history         INTEGER,
    require_complexity       BOOLEAN NOT NULL DEFAULT true,
    lock_after_failed_logins BOOLEAN NOT NULL DEFAULT true,
    ip_allowlist             TEXT[],          -- CIDRs (one per line in the UI)

    is_active                BOOLEAN NOT NULL DEFAULT true,
    created_at               TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by               UUID
);

CREATE INDEX IF NOT EXISTS ix_security_tenant_id ON security(tenant_id);
CREATE INDEX IF NOT EXISTS ix_security_security_id ON security(security_id);
