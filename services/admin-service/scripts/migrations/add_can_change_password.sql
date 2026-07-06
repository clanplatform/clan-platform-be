-- Adds the can_change_password column that drives the first-login flow:
--   true  → forced password change on first login (tenant-admin style)
--   false → user logs straight in and is redirected to the tenant app
--
-- Run against:
--   1. The master DB (clan_platform)
--   2. EVERY existing tenant DB (clan_platform_<code>...)
--   3. The auth-service DB (auth_service) — use the auth_users statement
--
-- New tenant DBs provisioned after this change get the column automatically.

-- Master DB and each tenant DB:
ALTER TABLE usersetup_basic
    ADD COLUMN IF NOT EXISTS can_change_password BOOLEAN NOT NULL DEFAULT true;

-- Auth-service DB (auth_service):
-- ALTER TABLE auth_users
--     ADD COLUMN IF NOT EXISTS can_change_password BOOLEAN NOT NULL DEFAULT true;
