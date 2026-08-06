-- Rename usersetup_basic.default_entity -> entity_id.
--
-- entity_id is the FK to entities.entity_id (the entities table's primary
-- key) and is the "Branch / location" field on the Users form. Renamed for
-- naming consistency with onboarding's OnboardingUser.entity_id and with the
-- rest of the schema (departments/divisions/job_codes all use entity_id).
--
-- Idempotent. Run against every usersetup_basic-bearing database (master +
-- each tenant DB):
--   psql -U postgres -d clan_platform          -f rename_usersetup_basic_default_entity_to_entity_id.sql
--   psql -U postgres -d clan_platform_<tenant> -f rename_usersetup_basic_default_entity_to_entity_id.sql

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'usersetup_basic' AND column_name = 'default_entity'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'usersetup_basic' AND column_name = 'entity_id'
    ) THEN
        ALTER TABLE usersetup_basic RENAME COLUMN default_entity TO entity_id;
    END IF;
END $$;
