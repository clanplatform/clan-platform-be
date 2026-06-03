-- ================================================
-- Migration: 003_create_menus_table.sql
-- Description: Create menus table for application navigation hierarchy
-- Author: Admin Service Team
-- Date: 2024
-- ================================================

-- Create menus table
CREATE TABLE IF NOT EXISTS menus (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    parent_menu_id UUID REFERENCES menus(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    key VARCHAR(100) NOT NULL,
    label VARCHAR(100),
    icon VARCHAR(100),
    menus_description TEXT,
    badge VARCHAR(50),
    section_title VARCHAR(200),
    route VARCHAR(200),
    component VARCHAR(200),
    level INTEGER DEFAULT 1,
    order_index INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    
    -- Constraint to prevent self-referencing
    CONSTRAINT menus_no_self_reference CHECK (id != parent_menu_id)
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_menus_application_id ON menus(application_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_menus_parent_menu_id ON menus(parent_menu_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_menus_key ON menus(key) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_menus_is_active ON menus(is_active) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_menus_order_index ON menus(order_index);
CREATE INDEX IF NOT EXISTS idx_menus_created_at ON menus(created_at DESC);

-- Create composite index for application + parent + order
CREATE INDEX IF NOT EXISTS idx_menus_app_parent_order ON menus(application_id, parent_menu_id, order_index) WHERE deleted_at IS NULL;

-- Create composite index for hierarchical queries
CREATE INDEX IF NOT EXISTS idx_menus_hierarchy ON menus(application_id, parent_menu_id, level) WHERE deleted_at IS NULL;

-- Add comments for documentation
COMMENT ON TABLE menus IS 'Hierarchical menu structure for applications';
COMMENT ON COLUMN menus.id IS 'Unique identifier (UUID)';
COMMENT ON COLUMN menus.application_id IS 'Foreign key to applications table';
COMMENT ON COLUMN menus.parent_menu_id IS 'Parent menu ID for hierarchy (NULL for top-level)';
COMMENT ON COLUMN menus.name IS 'Menu item name';
COMMENT ON COLUMN menus.key IS 'Unique key for menu item';
COMMENT ON COLUMN menus.label IS 'Display label';
COMMENT ON COLUMN menus.icon IS 'Icon identifier';
COMMENT ON COLUMN menus.menus_description IS 'Menu description';
COMMENT ON COLUMN menus.badge IS 'Badge text';
COMMENT ON COLUMN menus.section_title IS 'Section title for grouping';
COMMENT ON COLUMN menus.route IS 'Route/URL path';
COMMENT ON COLUMN menus.component IS 'Component identifier';
COMMENT ON COLUMN menus.level IS 'Hierarchy level (1=top-level, 2=submenu, etc.)';
COMMENT ON COLUMN menus.order_index IS 'Display order within parent';
COMMENT ON COLUMN menus.is_active IS 'Whether the menu item is active';
COMMENT ON COLUMN menus.deleted_at IS 'Soft delete timestamp';
COMMENT ON COLUMN menus.created_at IS 'Timestamp when menu was created';
