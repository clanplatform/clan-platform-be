-- Migration: Entity scoping and role client-scoping
-- Revision ID: 002
-- Create Date: 2026-06-22
-- Description:
--   1. Make entity_id NOT NULL on departments and divisions
--   2. Add client_id to userrole_basic and replace global unique constraints
--      with per-client unique constraints on role_name and role_code

-- ============================================================================
-- UPGRADE
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Step 1: departments.entity_id NOT NULL
-- Before running: ensure all existing rows have a valid entity_id.
-- Run this check first:
--   SELECT COUNT(*) FROM departments WHERE entity_id IS NULL;
-- If count > 0, update those rows:
--   UPDATE departments SET entity_id = '<default-entity-uuid>' WHERE entity_id IS NULL;
-- ----------------------------------------------------------------------------
ALTER TABLE departments
    ALTER COLUMN entity_id SET NOT NULL;

-- ----------------------------------------------------------------------------
-- Step 2: divisions.entity_id NOT NULL
-- Before running: ensure all existing rows have a valid entity_id.
-- Run this check first:
--   SELECT COUNT(*) FROM divisions WHERE entity_id IS NULL;
-- If count > 0, update those rows:
--   UPDATE divisions SET entity_id = '<default-entity-uuid>' WHERE entity_id IS NULL;
-- ----------------------------------------------------------------------------
ALTER TABLE divisions
    ALTER COLUMN entity_id SET NOT NULL;

-- ----------------------------------------------------------------------------
-- Step 3: Add client_id to userrole_basic
-- ----------------------------------------------------------------------------
ALTER TABLE userrole_basic
    ADD COLUMN IF NOT EXISTS client_id UUID REFERENCES clients(client_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_userrole_basic_client_id ON userrole_basic(client_id);

-- ----------------------------------------------------------------------------
-- Step 4: Replace global unique constraints with per-client constraints
-- The old constraints (role_name unique, role_code unique) are global.
-- New constraints allow the same name/code across different clients.
-- ----------------------------------------------------------------------------

-- Drop old global unique constraints
ALTER TABLE userrole_basic
    DROP CONSTRAINT IF EXISTS userrole_basic_role_name_key;

ALTER TABLE userrole_basic
    DROP CONSTRAINT IF EXISTS userrole_basic_role_code_key;

-- Add per-client unique constraints
ALTER TABLE userrole_basic
    ADD CONSTRAINT uq_userrole_basic_client_role_name UNIQUE (client_id, role_name);

ALTER TABLE userrole_basic
    ADD CONSTRAINT uq_userrole_basic_client_role_code UNIQUE (client_id, role_code);

-- ============================================================================
-- DOWNGRADE (Rollback)
-- ============================================================================

-- Uncomment to rollback:

-- ALTER TABLE userrole_basic DROP CONSTRAINT IF EXISTS uq_userrole_basic_client_role_code;
-- ALTER TABLE userrole_basic DROP CONSTRAINT IF EXISTS uq_userrole_basic_client_role_name;
-- ALTER TABLE userrole_basic ADD CONSTRAINT userrole_basic_role_code_key UNIQUE (role_code);
-- ALTER TABLE userrole_basic ADD CONSTRAINT userrole_basic_role_name_key UNIQUE (role_name);
-- DROP INDEX IF EXISTS ix_userrole_basic_client_id;
-- ALTER TABLE userrole_basic DROP COLUMN IF EXISTS client_id;
-- ALTER TABLE divisions ALTER COLUMN entity_id DROP NOT NULL;
-- ALTER TABLE departments ALTER COLUMN entity_id DROP NOT NULL;
