-- Adds the is_selling flag to the applications and modules tables so the
-- store / navigation UI can tell which apps and modules are offered for sale,
-- independently of is_active (licensed / enabled) and nav_group.
--
-- applications and modules live in the master DB (clan_platform) and in every
-- tenant DB (clan_platform_<code>...), so run this against:
--   1. The master DB (clan_platform) — also covered by alembic revision 041.
--   2. EVERY existing tenant DB — alembic only manages the master DB, so
--      already-provisioned tenant DBs need this run directly against them.
-- New tenant DBs provisioned after this change get the column from the
-- Application / Module models automatically (create_all() at provisioning).
--
-- Idempotent: ADD COLUMN IF NOT EXISTS, and ALTER TABLE IF EXISTS skips
-- databases without the table.

ALTER TABLE IF EXISTS applications ADD COLUMN IF NOT EXISTS is_selling BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE IF EXISTS modules      ADD COLUMN IF NOT EXISTS is_selling BOOLEAN NOT NULL DEFAULT FALSE;
