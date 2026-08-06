-- Drop usersetup_basic.entities (the old array fallback column).
--
-- usersetup_basic had two overlapping entity fields: entities (uuid[]) and
-- entity_id (uuid, FK -> entities.entity_id). entity_id is the single source
-- of truth ("Branch / location"); entities was only ever a backend fallback
-- read by get_audit_org_context() and is no longer written or read anywhere.
--
-- Idempotent. Run against every usersetup_basic-bearing database (master +
-- each tenant DB):
--   psql -U postgres -d clan_platform          -f drop_usersetup_basic_entities_array.sql
--   psql -U postgres -d clan_platform_<tenant> -f drop_usersetup_basic_entities_array.sql

ALTER TABLE IF EXISTS usersetup_basic DROP COLUMN IF EXISTS entities;
