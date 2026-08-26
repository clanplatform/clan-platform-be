-- Extends the entities (branches) table with the localization defaults a
-- branch can either set itself or inherit from its tenant when
-- tenants.use_default_localization=true (see create_entity()). time_zone
-- and date_format already existed; this adds the remaining 4.
--
-- entities lives in every tenant DB (and the master DB), so run against:
--   1. The master DB (clan_platform) — also covered by alembic revision 032.
--   2. EVERY existing tenant DB (clan_platform_<code>...) — alembic only
--      manages the master DB, so already-provisioned tenant DBs need this
--      run directly against them.
-- New tenant DBs provisioned after this change get the columns from the
-- Entity model automatically (create_all() at provisioning time).
--
-- Idempotent: ADD COLUMN IF NOT EXISTS, and ALTER TABLE IF EXISTS skips
-- databases without the table.

ALTER TABLE IF EXISTS entities ADD COLUMN IF NOT EXISTS default_language  VARCHAR(50);
ALTER TABLE IF EXISTS entities ADD COLUMN IF NOT EXISTS default_currency  VARCHAR(10);
ALTER TABLE IF EXISTS entities ADD COLUMN IF NOT EXISTS fiscal_year_start VARCHAR(20);
ALTER TABLE IF EXISTS entities ADD COLUMN IF NOT EXISTS week_starts_on    VARCHAR(20);
