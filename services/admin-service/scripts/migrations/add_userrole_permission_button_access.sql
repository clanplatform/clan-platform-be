-- Add button-permission columns to userrole_permission.
--
-- The role "Access" panel has three tabs — Menu / Form / Button access. Menu
-- lived on this table (menu_permissions + menu_access); Button access is now
-- modelled the same way (per the chosen "add to userrole_permission" design):
--   button_permissions JSONB  [{"id": button-uuid, "access": ["read","write"]}]
--   button_access       highest level ('read' | 'write' | 'disable')
--
-- Idempotent. Run against every userrole_permission-bearing database (master +
-- each tenant DB), e.g.:
--   psql -U postgres -d clan_platform          -f add_userrole_permission_button_access.sql
--   psql -U postgres -d clan_platform_<tenant> -f add_userrole_permission_button_access.sql

ALTER TABLE IF EXISTS userrole_permission
    ADD COLUMN IF NOT EXISTS button_permissions JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE IF EXISTS userrole_permission
    ADD COLUMN IF NOT EXISTS button_access VARCHAR(50) DEFAULT 'disable';
