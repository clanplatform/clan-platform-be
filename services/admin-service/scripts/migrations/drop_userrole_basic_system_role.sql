-- Drop userrole_basic.system_role.
--
-- The "system role" flag is not part of the role form (screenshot) and had no
-- service/route logic — removed from the schema and model. This drops the now-
-- orphaned column. (The model column is NOT NULL with no server default, so it
-- must be dropped or inserts that no longer supply it would fail.)
--
-- Idempotent. Run against every userrole_basic-bearing database (master +
-- each tenant DB), e.g.:
--   psql -U postgres -d clan_platform          -f drop_userrole_basic_system_role.sql
--   psql -U postgres -d clan_platform_<tenant> -f drop_userrole_basic_system_role.sql

ALTER TABLE IF EXISTS userrole_basic DROP COLUMN IF EXISTS system_role;
