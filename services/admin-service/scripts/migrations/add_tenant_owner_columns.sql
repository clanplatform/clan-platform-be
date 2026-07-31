-- Adds tenants.owner_name and tenants.owner_email — the account owner's name
-- and email, denormalized onto the tenant record for display/reference.
--
-- The owner's login PASSWORD is intentionally NOT stored on the tenant — it is
-- hashed on the owner user (usersetup_basic.password_hash). The onboarding
-- "Initial status" maps to the existing tenants.is_active column (no new column).
--
-- tenants lives in the master DB and is copied into every tenant DB, so run
-- against:
--   1. The master DB (clan_platform)
--   2. EVERY existing tenant DB (clan_platform_<code>...)
--
-- Idempotent: ADD COLUMN IF NOT EXISTS, and ALTER TABLE IF EXISTS skips
-- databases without the table.

ALTER TABLE IF EXISTS tenants ADD COLUMN IF NOT EXISTS owner_name  VARCHAR(200);
ALTER TABLE IF EXISTS tenants ADD COLUMN IF NOT EXISTS owner_email VARCHAR(255);
