-- Adds department_head (Head / manager name) to the departments table — the one
-- new field on the onboarding "Add department" form. All other form fields map
-- to existing columns (department_name, department_code, entity_id/branch,
-- department_type, cost_center, location, phone, email, annual_budget, and
-- "Reports to" -> parent_department_id / reporting_structure).
--
-- departments lives in every tenant DB (and the master DB), so run against:
--   1. The master DB (clan_platform)
--   2. EVERY existing tenant DB (clan_platform_<code>...)
-- New tenant DBs provisioned after this change get the column from the models.
--
-- Idempotent: ADD COLUMN IF NOT EXISTS, and ALTER TABLE IF EXISTS skips
-- databases without the table.

ALTER TABLE IF EXISTS departments ADD COLUMN IF NOT EXISTS department_head VARCHAR(100);
