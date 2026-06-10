-- Migration: Create user_role_form_permission table
-- Revision ID: 001
-- Create Date: 2026-06-09
-- Description: Creates the user_role_form_permission table with all required columns,
--              foreign keys, indexes, sequence, and triggers

-- ============================================================================
-- UPGRADE
-- ============================================================================

-- Create sequence for sino column
CREATE SEQUENCE IF NOT EXISTS role_form_permission_sino_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

-- Create the user_role_form_permission table
CREATE TABLE IF NOT EXISTS user_role_form_permission (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Serial number for ordering/display (auto-incremented)
    sino INTEGER NOT NULL UNIQUE DEFAULT nextval('role_form_permission_sino_seq'::regclass),
    
    -- Foreign keys to user role tables
    user_role_id UUID NOT NULL REFERENCES user_role(id) ON DELETE CASCADE,
    userrole_basic_id UUID NOT NULL REFERENCES userrole_basic(id) ON DELETE CASCADE,
    userrole_permission_id UUID NOT NULL REFERENCES userrole_permission(id) ON DELETE CASCADE,
    
    -- Form permissions stored as JSONB array
    -- Structure: [{"id": "form-uuid", "application_id": "app-uuid", "modules_id": "module-uuid", "access": ["read", "write"]}]
    form_permissions JSONB NOT NULL DEFAULT '[]'::jsonb,
    
    -- Highest form access level (calculated from form_permissions array)
    -- Values: 'read', 'write', 'disable'
    form_access VARCHAR(20) DEFAULT 'disable',
    
    -- Timestamps
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS ix_user_role_form_permission_id 
    ON user_role_form_permission(id);

CREATE INDEX IF NOT EXISTS ix_user_role_form_permission_sino 
    ON user_role_form_permission(sino);

CREATE INDEX IF NOT EXISTS ix_user_role_form_permission_user_role_id 
    ON user_role_form_permission(user_role_id);

CREATE INDEX IF NOT EXISTS ix_user_role_form_permission_userrole_basic_id 
    ON user_role_form_permission(userrole_basic_id);

CREATE INDEX IF NOT EXISTS ix_user_role_form_permission_userrole_permission_id 
    ON user_role_form_permission(userrole_permission_id);

-- Create trigger function for updated_at
CREATE OR REPLACE FUNCTION update_user_role_form_permission_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to automatically update updated_at timestamp
CREATE TRIGGER trigger_user_role_form_permission_updated_at
    BEFORE UPDATE ON user_role_form_permission
    FOR EACH ROW
    EXECUTE FUNCTION update_user_role_form_permission_updated_at();

-- Add table comment
COMMENT ON TABLE user_role_form_permission IS 
    'Stores form permissions for user roles separately from menu permissions';

-- Add column comments
COMMENT ON COLUMN user_role_form_permission.id IS 
    'Primary key UUID';
COMMENT ON COLUMN user_role_form_permission.sino IS 
    'Serial number for ordering';
COMMENT ON COLUMN user_role_form_permission.user_role_id IS 
    'Reference to user_role (UserRoleMain) table';
COMMENT ON COLUMN user_role_form_permission.userrole_basic_id IS 
    'Reference to userrole_basic table';
COMMENT ON COLUMN user_role_form_permission.userrole_permission_id IS 
    'Reference to userrole_permission table (required - to get menu selections)';
COMMENT ON COLUMN user_role_form_permission.form_permissions IS 
    'Array of form permissions with individual access levels';
COMMENT ON COLUMN user_role_form_permission.form_access IS 
    'Highest form access level: read, write, or disable';

-- ============================================================================
-- DOWNGRADE (Rollback script)
-- ============================================================================

-- Uncomment the following lines to rollback this migration:

-- DROP TRIGGER IF EXISTS trigger_user_role_form_permission_updated_at ON user_role_form_permission;
-- DROP FUNCTION IF EXISTS update_user_role_form_permission_updated_at();
-- DROP TABLE IF EXISTS user_role_form_permission CASCADE;
-- DROP SEQUENCE IF EXISTS role_form_permission_sino_seq;
