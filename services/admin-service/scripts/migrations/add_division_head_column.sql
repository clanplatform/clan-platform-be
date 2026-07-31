-- Adds division_head (Head / lead name) to the divisions table — the one new
-- field on the onboarding "Add division" form. All other form fields map to
-- existing columns (division_name, division_code, entity_id/branch,
-- department_id/parent department, hierarchy_level, description).
--
-- divisions lives in every tenant DB (and the master DB), so run against:
--   1. The master DB (clan_platform)
--   2. EVERY existing tenant DB (clan_platform_<code>...)
-- New tenant DBs provisioned after this change get the column from the models.
--
-- Idempotent: ADD COLUMN IF NOT EXISTS, and ALTER TABLE IF EXISTS skips
-- databases without the table.

ALTER TABLE IF EXISTS divisions ADD COLUMN IF NOT EXISTS division_head VARCHAR(100);
