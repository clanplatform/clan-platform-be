-- Removes the tenants.tenant_db_name column. The dedicated database name is now
-- derived from tenant_code (Tenant.tenant_db_name is a computed property:
-- clan_platform_<slug(tenant_code)>), so it is no longer stored.
--
-- table_permission, allowed_origins and is_active stay as columns (they are
-- backend-managed / operational) — only tenant_db_name is dropped.
--
-- tenants lives in the master DB and is copied into every tenant DB, so run
-- against:
--   1. The master DB (clan_platform)
--   2. EVERY existing tenant DB (clan_platform_<code>...)
--
-- Idempotent: DROP COLUMN IF EXISTS, and ALTER TABLE IF EXISTS skips databases
-- without the table.

ALTER TABLE IF EXISTS tenants DROP COLUMN IF EXISTS tenant_db_name;
