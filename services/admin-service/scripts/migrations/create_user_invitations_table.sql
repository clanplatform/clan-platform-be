-- Creates the user_invitations table — invitation-email tracking for
-- user_setup users (POST /api/v1/user_setup/{user_id}/send-invitation and
-- the selected/bulk variants).
--
-- The table is defined by app/user_invitations/models/user_invitations.py
-- and is created automatically in freshly provisioned tenant DBs (and at
-- startup in the master DB) via Base.metadata.create_all. This script
-- provisions it for databases that already exist. Run against:
--   1. The master DB (clan_platform)
--   2. EVERY existing tenant DB (clan_platform_<code>...)
--
-- Idempotent: CREATE TABLE / CREATE INDEX IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS user_invitations (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES user_setup(id) ON DELETE CASCADE,
    tenant_id     UUID REFERENCES tenants(tenant_id),
    email         VARCHAR(255) NOT NULL,
    token_hash    VARCHAR(64) NOT NULL,
    expires_at    TIMESTAMP WITH TIME ZONE NOT NULL,
    status        VARCHAR(20) NOT NULL DEFAULT 'pending',
    sent_at       TIMESTAMP WITH TIME ZONE,
    accepted_at   TIMESTAMP WITH TIME ZONE,
    created_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_user_invitations_token_hash UNIQUE (token_hash)
);

CREATE INDEX IF NOT EXISTS ix_user_invitations_user_id ON user_invitations(user_id);
CREATE INDEX IF NOT EXISTS ix_user_invitations_tenant_id ON user_invitations(tenant_id);
CREATE INDEX IF NOT EXISTS ix_user_invitations_status ON user_invitations(status);
CREATE INDEX IF NOT EXISTS ix_user_invitations_token_hash ON user_invitations(token_hash);
