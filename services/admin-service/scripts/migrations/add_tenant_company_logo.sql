-- Adds tenants.company_logo (logo URL / file reference).
--
-- owner_full_name and initial_status are onboarding-only inputs (owner_full_name
-- names the first admin user; initial_status maps to the existing is_active
-- column), so no new columns are needed for those.
--
-- tenants lives in the master DB and is copied into every tenant DB, so run
-- against:
--   1. The master DB (clan_platform)
--   2. EVERY existing tenant DB (clan_platform_<code>...)
--
-- Idempotent: ADD COLUMN IF NOT EXISTS, and ALTER TABLE IF EXISTS skips
-- databases without the table.

ALTER TABLE IF EXISTS tenants ADD COLUMN IF NOT EXISTS company_logo VARCHAR(500);
