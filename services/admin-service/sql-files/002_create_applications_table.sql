-- ================================================
-- Migration: 002_create_applications_table.sql
-- Description: Create applications table for domain applications
-- Author: Admin Service Team
-- Date: 2024
-- ================================================

-- Create applications table
CREATE TABLE IF NOT EXISTS applications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    domain_id UUID NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    version VARCHAR(20) DEFAULT '1.0.0',
    status VARCHAR(50) DEFAULT 'active',
    config JSONB DEFAULT '{}'::jsonb,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    is_deleted BOOLEAN DEFAULT FALSE NOT NULL,
    deleted_at TIMESTAMPTZ,
    
    -- Navigation/UI fields
    key VARCHAR(100),
    label VARCHAR(100),
    route VARCHAR(200),
    level INTEGER DEFAULT 1,
    icon VARCHAR(100),
    badge VARCHAR(50),
    section_title VARCHAR(200),
    access TEXT[],  -- Array of access permissions
    order_index INTEGER DEFAULT 0,
    
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_applications_domain_id ON applications(domain_id) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_applications_name ON applications(name) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_applications_is_active ON applications(is_active) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_applications_is_deleted ON applications(is_deleted);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_applications_created_at ON applications(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_applications_order_index ON applications(order_index);
CREATE INDEX IF NOT EXISTS idx_applications_key ON applications(key) WHERE is_deleted = FALSE;

-- Create composite index for domain + order
CREATE INDEX IF NOT EXISTS idx_applications_domain_order ON applications(domain_id, order_index) WHERE is_deleted = FALSE;

-- Create trigger for applications table
DROP TRIGGER IF EXISTS update_applications_updated_at ON applications;
CREATE TRIGGER update_applications_updated_at
    BEFORE UPDATE ON applications
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE applications IS 'Applications within domains';
COMMENT ON COLUMN applications.id IS 'Unique identifier (UUID)';
COMMENT ON COLUMN applications.domain_id IS 'Foreign key to domains table';
COMMENT ON COLUMN applications.name IS 'Application name';
COMMENT ON COLUMN applications.description IS 'Application description';
COMMENT ON COLUMN applications.version IS 'Application version';
COMMENT ON COLUMN applications.status IS 'Application status (active, inactive, etc.)';
COMMENT ON COLUMN applications.config IS 'Application configuration as JSON';
COMMENT ON COLUMN applications.is_active IS 'Whether the application is active';
COMMENT ON COLUMN applications.is_deleted IS 'Soft delete flag';
COMMENT ON COLUMN applications.deleted_at IS 'Timestamp when application was deleted';
COMMENT ON COLUMN applications.key IS 'Application key for navigation';
COMMENT ON COLUMN applications.label IS 'Display label for UI';
COMMENT ON COLUMN applications.route IS 'Application route/URL path';
COMMENT ON COLUMN applications.level IS 'Hierarchy level';
COMMENT ON COLUMN applications.icon IS 'Icon identifier';
COMMENT ON COLUMN applications.badge IS 'Badge text';
COMMENT ON COLUMN applications.section_title IS 'Section title for grouping';
COMMENT ON COLUMN applications.access IS 'Array of access permissions';
COMMENT ON COLUMN applications.order_index IS 'Display order';
COMMENT ON COLUMN applications.created_at IS 'Timestamp when application was created';
COMMENT ON COLUMN applications.updated_at IS 'Timestamp when application was last updated';
