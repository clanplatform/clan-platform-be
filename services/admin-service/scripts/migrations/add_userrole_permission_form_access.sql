-- Add form-permission columns to userrole_permission.
--
-- The role "Access" panel has three tabs — Menu / Form / Button access. Menu and
-- Button already live on this table; Form access is now unified here too (same
-- design), so all three are created/read with the role:
--   form_permissions JSONB  [{"id": form-uuid, "application_id": "...", "modules_id": "...", "access": ["read","write"]}]
--   form_access       highest level ('read' | 'write' | 'disable')
--
-- NOTE: the standalone user_role_form_permission table still exists and keeps
-- working via its own endpoints; these columns are the unified home for form
-- access alongside menu/button.
--
-- Idempotent. Run against every userrole_permission-bearing database (master +
-- each tenant DB), e.g.:
--   psql -U postgres -d clan_platform          -f add_userrole_permission_form_access.sql
--   psql -U postgres -d clan_platform_<tenant> -f add_userrole_permission_form_access.sql

ALTER TABLE IF EXISTS userrole_permission
    ADD COLUMN IF NOT EXISTS form_permissions JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE IF EXISTS userrole_permission
    ADD COLUMN IF NOT EXISTS form_access VARCHAR(50) DEFAULT 'disable';
