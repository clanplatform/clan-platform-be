-- Adds grade_band and salary_currency to jobcode_basicinfo — the two new fields
-- on the onboarding "Add job code" form. All other form fields map to existing
-- columns (job_code, job_title, entity_id/branch, department_id, division_id,
-- employment_type, work_mode, minimum_salary, maximum_salary, experience_years,
-- reports_to, required_skills, key_responsibilities).
--
-- jobcode_basicinfo lives in every tenant DB (and the master DB), so run against:
--   1. The master DB (clan_platform)
--   2. EVERY existing tenant DB (clan_platform_<code>...)
-- New tenant DBs provisioned after this change get the columns from the models.
--
-- Idempotent: ADD COLUMN IF NOT EXISTS, and ALTER TABLE IF EXISTS skips
-- databases without the table.

ALTER TABLE IF EXISTS jobcode_basicinfo ADD COLUMN IF NOT EXISTS grade_band      VARCHAR(50);
ALTER TABLE IF EXISTS jobcode_basicinfo ADD COLUMN IF NOT EXISTS salary_currency VARCHAR(10);
