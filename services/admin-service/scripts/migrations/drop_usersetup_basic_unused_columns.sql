-- Drop usersetup_basic columns not on the "Add user" screen and with no other
-- backend consumer:
--   start_date, end_date, tem_employee   — employment metadata, unused anywhere
--   department, division, job_code       — org-structure refs, unused anywhere
--   default_dept                         — unused anywhere
--   manage_roles                         — "roles this user can manage"; only
--                                           self-referential validation, no
--                                           other reader
--   reporting_to                         — self-referencing FK; only
--                                           self-referential validation, no
--                                           other reader
--   view, dashboard_view                 — UI preferences, unused anywhere
--
-- Kept (NOT dropped, still backend-relevant):
--   entities        — fallback array read by get_audit_org_context()
--   tenant_id       — JWT-derived tenant scoping (hidden from schema, not removed)
--   can_change_password — first-login password-change flag (hidden from
--                          schema, always true at creation; consumed by the
--                          auth-service login flow)
--
-- Idempotent / destructive. Run against every usersetup_basic-bearing database
-- (master + each tenant DB), e.g.:
--   psql -U postgres -d clan_platform          -f drop_usersetup_basic_unused_columns.sql
--   psql -U postgres -d clan_platform_<tenant> -f drop_usersetup_basic_unused_columns.sql

ALTER TABLE IF EXISTS usersetup_basic DROP COLUMN IF EXISTS start_date;
ALTER TABLE IF EXISTS usersetup_basic DROP COLUMN IF EXISTS end_date;
ALTER TABLE IF EXISTS usersetup_basic DROP COLUMN IF EXISTS tem_employee;
ALTER TABLE IF EXISTS usersetup_basic DROP COLUMN IF EXISTS department;
ALTER TABLE IF EXISTS usersetup_basic DROP COLUMN IF EXISTS division;
ALTER TABLE IF EXISTS usersetup_basic DROP COLUMN IF EXISTS job_code;
ALTER TABLE IF EXISTS usersetup_basic DROP COLUMN IF EXISTS default_dept;
ALTER TABLE IF EXISTS usersetup_basic DROP COLUMN IF EXISTS manage_roles;
ALTER TABLE IF EXISTS usersetup_basic DROP COLUMN IF EXISTS reporting_to;
ALTER TABLE IF EXISTS usersetup_basic DROP COLUMN IF EXISTS "view";
ALTER TABLE IF EXISTS usersetup_basic DROP COLUMN IF EXISTS dashboard_view;
