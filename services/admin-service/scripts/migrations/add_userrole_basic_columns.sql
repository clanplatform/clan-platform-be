-- Adds three fields to userrole_basic from the onboarding "Add role" form:
--   parent_role_id        -> "Reports to (parent role)" — the parent role's
--                            user_role.id (bare UUID, no FK: userrole_basic
--                            already has one FK to user_role.id and a second
--                            would make the ORM relationship ambiguous)
--   access_scope          -> "Access scope"
--   default_for_new_users -> "Default for new users"
-- All other form fields map to existing columns (role_name, role_code,
-- role_level = hierarchy level, description, is_admin = administrator role, active).
--
-- userrole_basic lives in every tenant DB (and the master DB), so run against:
--   1. The master DB (clan_platform)
--   2. EVERY existing tenant DB (clan_platform_<code>...)
-- New tenant DBs provisioned after this change get the columns from the models.
--
-- Idempotent: ADD COLUMN IF NOT EXISTS, and ALTER TABLE IF EXISTS skips
-- databases without the table.

ALTER TABLE IF EXISTS userrole_basic ADD COLUMN IF NOT EXISTS parent_role_id        UUID;
ALTER TABLE IF EXISTS userrole_basic ADD COLUMN IF NOT EXISTS access_scope          VARCHAR(50);
ALTER TABLE IF EXISTS userrole_basic ADD COLUMN IF NOT EXISTS default_for_new_users BOOLEAN NOT NULL DEFAULT false;
