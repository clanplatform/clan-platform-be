-- Drop the standalone user_role_form_permission table.
--
-- Form access is now unified on userrole_permission (form_permissions +
-- form_access), alongside menu and button access. The separate
-- user_role_form_permission module (model/schema/service/routes) has been
-- removed, so its table + serial sequence are dropped here.
--
-- Idempotent / destructive. Run against every database that had it (master +
-- each tenant DB), e.g.:
--   psql -U postgres -d clan_platform          -f drop_user_role_form_permission_table.sql
--   psql -U postgres -d clan_platform_<tenant> -f drop_user_role_form_permission_table.sql

DROP TABLE IF EXISTS user_role_form_permission CASCADE;
DROP SEQUENCE IF EXISTS role_form_permission_sino_seq;
