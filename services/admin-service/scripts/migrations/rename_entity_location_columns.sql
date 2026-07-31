-- Renames the entity location columns to match the UI (they hold names, not
-- codes) and widens them from VARCHAR(10):
--   city_code    -> city    VARCHAR(100)
--   state_code   -> state   VARCHAR(100)
--   country_code -> country VARCHAR(100)
--
-- entities lives in every tenant DB (and the master DB), so run against:
--   1. The master DB (clan_platform)
--   2. EVERY existing tenant DB (clan_platform_<code>...)
--
-- Idempotent: renames only when the old column exists and the new one does not,
-- then widens (a no-op if already VARCHAR(100)).

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='entities' AND column_name='city_code')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='entities' AND column_name='city') THEN
        ALTER TABLE entities RENAME COLUMN city_code TO city;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='entities' AND column_name='state_code')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='entities' AND column_name='state') THEN
        ALTER TABLE entities RENAME COLUMN state_code TO state;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='entities' AND column_name='country_code')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='entities' AND column_name='country') THEN
        ALTER TABLE entities RENAME COLUMN country_code TO country;
    END IF;
END $$;

ALTER TABLE IF EXISTS entities ALTER COLUMN city    TYPE VARCHAR(100);
ALTER TABLE IF EXISTS entities ALTER COLUMN state   TYPE VARCHAR(100);
ALTER TABLE IF EXISTS entities ALTER COLUMN country TYPE VARCHAR(100);
