-- ================================================
-- Migration: 001_create_domains_table.sql
-- Description: Create domains table for platform domains
-- Author: Admin Service Team
-- Date: 2024
-- ================================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create domains table
CREATE TABLE IF NOT EXISTS domains (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    domain_metadata JSONB DEFAULT '{}'::jsonb,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    is_deleted BOOLEAN DEFAULT FALSE NOT NULL,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_domains_code ON domains(code) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_domains_name ON domains(name) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_domains_is_active ON domains(is_active) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_domains_is_deleted ON domains(is_deleted);
CREATE INDEX IF NOT EXISTS idx_domains_created_at ON domains(created_at DESC);

-- Create trigger function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for domains table
DROP TRIGGER IF EXISTS update_domains_updated_at ON domains;
CREATE TRIGGER update_domains_updated_at
    BEFORE UPDATE ON domains
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE domains IS 'Platform domains that contain applications';
COMMENT ON COLUMN domains.id IS 'Unique identifier (UUID)';
COMMENT ON COLUMN domains.code IS 'Domain code (1-50 characters, unique)';
COMMENT ON COLUMN domains.name IS 'Domain name (1-100 characters, unique)';
COMMENT ON COLUMN domains.description IS 'Domain description';
COMMENT ON COLUMN domains.domain_metadata IS 'Additional metadata as JSON';
COMMENT ON COLUMN domains.is_active IS 'Whether the domain is active';
COMMENT ON COLUMN domains.is_deleted IS 'Soft delete flag';
COMMENT ON COLUMN domains.deleted_at IS 'Timestamp when domain was deleted';
COMMENT ON COLUMN domains.created_at IS 'Timestamp when domain was created';
COMMENT ON COLUMN domains.updated_at IS 'Timestamp when domain was last updated';
