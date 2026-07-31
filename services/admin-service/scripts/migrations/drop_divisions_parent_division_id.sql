-- Drop divisions.parent_division_id.
--
-- The self-referential "parent division" link was removed from the model,
-- schema and service — divisions now match the final form (branch, parent
-- department, division head, hierarchy level, description) with no parent-
-- division hierarchy. This drops the now-orphaned column (its self-FK to
-- divisions.id drops with it).
--
-- Idempotent. Run against every divisions-bearing database (master +
-- each tenant DB), e.g.:
--   psql -U postgres -d clan_platform            -f drop_divisions_parent_division_id.sql
--   psql -U postgres -d clan_platform_<tenant>   -f drop_divisions_parent_division_id.sql

ALTER TABLE IF EXISTS divisions DROP COLUMN IF EXISTS parent_division_id;
