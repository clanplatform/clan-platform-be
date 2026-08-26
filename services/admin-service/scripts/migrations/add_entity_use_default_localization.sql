-- Moves the "use the tenant's own localization defaults" flag from tenants
-- (tenant-wide) to entities (per-branch) — each branch now opts in
-- individually to inheriting the tenant's default_language/time_zone/
-- default_currency/date_format/fiscal_year_start/week_starts_on instead of
-- setting its own. See create_entity()'s use_default_localization check.
--
-- entities lives in every tenant DB (and the master DB), so run against:
--   1. The master DB (clan_platform) — also covered by alembic revision 033.
--   2. EVERY existing tenant DB (clan_platform_<code>...) — alembic only
--      manages the master DB, so already-provisioned tenant DBs need this
--      run directly against them.
-- New tenant DBs provisioned after this change get the column from the
-- Entity model automatically (create_all() at provisioning time).
--
-- Idempotent: ADD/DROP COLUMN IF (NOT) EXISTS, and ALTER TABLE IF EXISTS
-- skips databases without the table.

ALTER TABLE IF EXISTS entities ADD COLUMN IF NOT EXISTS use_default_localization BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE IF EXISTS tenants  DROP COLUMN IF EXISTS use_default_localization;
