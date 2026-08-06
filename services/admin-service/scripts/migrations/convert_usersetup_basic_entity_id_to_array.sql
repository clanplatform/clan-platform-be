-- Convert usersetup_basic.entity_id from a single UUID to UUID[] — one user
-- can now belong to multiple entities (branches). The first array element is
-- treated as the user's default/primary branch (audit context resolution).
--
-- Steps (idempotent, safe to re-run):
--   1. Drop the FK constraint (Postgres can't enforce a FK on array elements).
--   2. Convert the column type, wrapping any existing single value into a
--      1-element array (NULL stays NULL).
--
-- Run against every usersetup_basic-bearing database (master + each tenant DB):
--   psql -U postgres -d clan_platform          -f convert_usersetup_basic_entity_id_to_array.sql
--   psql -U postgres -d clan_platform_<tenant> -f convert_usersetup_basic_entity_id_to_array.sql

DO $$
BEGIN
    -- 1. Drop the FK constraint if the column is not already an array
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'usersetup_basic' AND column_name = 'entity_id' AND data_type = 'uuid'
    ) THEN
        ALTER TABLE usersetup_basic DROP CONSTRAINT IF EXISTS usersetup_basic_default_entity_fkey;
        ALTER TABLE usersetup_basic DROP CONSTRAINT IF EXISTS usersetup_basic_entity_id_fkey;

        -- 2. Convert to UUID[]
        ALTER TABLE usersetup_basic
            ALTER COLUMN entity_id TYPE UUID[]
            USING (CASE WHEN entity_id IS NULL THEN NULL ELSE ARRAY[entity_id] END);
    END IF;
END $$;
