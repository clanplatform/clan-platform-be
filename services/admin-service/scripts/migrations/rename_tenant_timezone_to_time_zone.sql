-- Unifies the timezone spelling on tenants to match entities: renames
-- tenants.timezone -> tenants.time_zone (the entities table already uses
-- time_zone / time_zone_offset).
--
-- tenants lives in the master DB and is copied into every tenant DB, so run
-- against:
--   1. The master DB (clan_platform)
--   2. EVERY existing tenant DB (clan_platform_<code>...)
--
-- Idempotent: only renames when the old column exists and the new one does not.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'tenants' AND column_name = 'timezone'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'tenants' AND column_name = 'time_zone'
    ) THEN
        ALTER TABLE tenants RENAME COLUMN timezone TO time_zone;
    END IF;
END $$;
