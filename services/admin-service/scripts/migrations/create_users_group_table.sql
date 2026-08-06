-- Create the users_group table (User groups: bundle users under a shared
-- default role).
--
-- Fields match the "User groups" screenshot: Group name, Group code,
-- Default role, Description. tenant_id and is_active are backend-operational
-- (JWT-derived / soft-delete flag) and are not part of the CRUD schema.
--
-- NOTE: admin-service auto-creates this table via SQLAlchemy's
-- Base.metadata.create_all(checkfirst=True) on next restart (the UserGroup
-- model is registered in session.py / tenant_db_manager.py), so this script is
-- mainly for explicitness / manual provisioning — it's idempotent either way.
--
-- Run against every database that should have this table (master + each
-- tenant DB):
--   psql -U postgres -d clan_platform          -f create_users_group_table.sql
--   psql -U postgres -d clan_platform_<tenant> -f create_users_group_table.sql

CREATE TABLE IF NOT EXISTS users_group (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(tenant_id),
    group_name VARCHAR(100) NOT NULL,
    group_code VARCHAR(50),
    default_role_id UUID REFERENCES user_role(id),
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
