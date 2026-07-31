-- Adds two fields to usersetup_basic from the onboarding "Add user" form:
--   user_group_id     -> "User group" (bare UUID reference; there is no
--                        user_groups table yet, so no FK)
--   send_invite_email -> "Send invite email" toggle
-- All other form fields map to existing columns (firstname, lastname,
-- employee_id, username, email, password_hash = temporary password,
-- phone_number, status, role via usersetup_roles_entity, branch via
-- entities/default_entity).
--
-- usersetup_basic lives in every tenant DB (and the master DB), so run against:
--   1. The master DB (clan_platform)
--   2. EVERY existing tenant DB (clan_platform_<code>...)
-- New tenant DBs provisioned after this change get the columns from the models.
--
-- Idempotent: ADD COLUMN IF NOT EXISTS, and ALTER TABLE IF EXISTS skips
-- databases without the table.

ALTER TABLE IF EXISTS usersetup_basic ADD COLUMN IF NOT EXISTS user_group_id     UUID;
ALTER TABLE IF EXISTS usersetup_basic ADD COLUMN IF NOT EXISTS send_invite_email BOOLEAN NOT NULL DEFAULT false;
