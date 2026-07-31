-- Trims departments to the onboarding "Add department" form fields:
--   * removes description (not a form field)
--   * removes parent_department_id (the department->parent-department hierarchy is
--     dropped; "Reports to" maps to reporting_structure). This also drops its
--     self-referencing FK.
--
-- departments lives in every tenant DB (and the master DB), so run against:
--   1. The master DB (clan_platform)
--   2. EVERY existing tenant DB (clan_platform_<code>...)
--
-- Idempotent: DROP COLUMN IF EXISTS, and ALTER TABLE IF EXISTS skips databases
-- without the table.

ALTER TABLE IF EXISTS departments DROP COLUMN IF EXISTS parent_department_id;
ALTER TABLE IF EXISTS departments DROP COLUMN IF EXISTS description;
