-- Makes tenant_id nullable on the org-structure tables so master-DB users can
-- create these rows. tenant_id is now derived from the JWT, never the request:
--   NULL     -> master-DB user (token has no tenant_id)
--   a tenant -> tenant-DB user (token's tenant_id)
--
-- Needed because Base.metadata.create_all only creates missing tables; it does
-- NOT relax NOT NULL on columns that already exist. Freshly provisioned (or
-- dropped-and-recreated) tenant DBs get the nullable column from the models
-- automatically — this script is only for databases that already have the
-- tables, above all the long-lived master DB.
--
-- Run against:
--   1. The master DB (clan_platform)
--   2. EVERY existing tenant DB (clan_platform_<code>...)
--
-- Idempotent: DROP NOT NULL on an already-nullable column is a no-op, and
-- ALTER TABLE IF EXISTS skips tables that are absent in a given database.

ALTER TABLE IF EXISTS entities          ALTER COLUMN tenant_id DROP NOT NULL;
ALTER TABLE IF EXISTS departments       ALTER COLUMN tenant_id DROP NOT NULL;
ALTER TABLE IF EXISTS divisions         ALTER COLUMN tenant_id DROP NOT NULL;
ALTER TABLE IF EXISTS job_codes         ALTER COLUMN tenant_id DROP NOT NULL;
ALTER TABLE IF EXISTS jobcode_basicinfo ALTER COLUMN tenant_id DROP NOT NULL;
