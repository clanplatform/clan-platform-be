-- ============================================================
-- Complete Identity Database Setup Script
-- This script creates the auth_service database and auth_users table
-- Run this on your PostgreSQL server (port 5433)
-- ============================================================

-- ==================== STEP 1: CREATE DATABASE ====================
-- Connect to postgres database first, then run this:
-- psql -h localhost -p 5433 -U postgres -d postgres -f create_identity_database.sql

-- Drop database if exists (CAREFUL - this deletes all data!)
-- Uncomment the next line only if you want to recreate from scratch
-- DROP DATABASE IF EXISTS auth_service;

-- Create the auth_service database
CREATE DATABASE auth_service
    WITH 
    OWNER = postgres
    ENCODING = 'UTF8'
    LC_COLLATE = 'en_US.utf8'
    LC_CTYPE = 'en_US.utf8'
    TABLESPACE = pg_default
    CONNECTION LIMIT = -1
    IS_TEMPLATE = False;

COMMENT ON DATABASE auth_service IS 'Identity/Authentication service database for user authentication sync';

-- ==================== STEP 2: CONNECT TO NEW DATABASE ====================
-- Now connect to the auth_service database:
-- \c auth_service

-- Or reconnect using:
-- psql -h localhost -p 5433 -U postgres -d auth_service

-- ==================== STEP 3: CREATE EXTENSIONS ====================

-- Create UUID extension for generating UUIDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

COMMENT ON EXTENSION "uuid-ossp" IS 'UUID generation functions';

-- ==================== STEP 4: CREATE auth_users TABLE ====================

-- Drop table if exists (for clean install)
-- Uncomment next line only if you want to recreate the table
-- DROP TABLE IF EXISTS auth_users CASCADE;

-- Create auth_users table with all required fields
CREATE TABLE IF NOT EXISTS auth_users (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Reference to admin service
    user_setup_id UUID,
    
    -- Basic user information
    firstname VARCHAR(100) NOT NULL,
    lastname VARCHAR(100) NOT NULL,
    employee_id VARCHAR(50) NOT NULL UNIQUE,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    phone_number VARCHAR(20),
    
    -- Authentication fields
    password_hash VARCHAR(255) NOT NULL,
    password_changed TIMESTAMP WITH TIME ZONE,
    is_password_change BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- User status
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    
    -- Employment details
    start_date DATE,
    end_date DATE,
    tem_employee BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Organizational structure (UUIDs reference admin service tables)
    department UUID,
    division UUID,
    job_code UUID,
    manage_roles UUID[],
    default_dept UUID,
    reporting_to UUID,
    entities UUID[],
    default_entity UUID,
    
    -- Preferences
    view VARCHAR(50),
    dashboard_view VARCHAR(50),
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ==================== STEP 5: CREATE INDEXES ====================

-- Index on username for fast login lookups
CREATE INDEX IF NOT EXISTS idx_auth_users_username ON auth_users(username);

-- Index on email for fast email lookups
CREATE INDEX IF NOT EXISTS idx_auth_users_email ON auth_users(email);

-- Index on employee_id for fast employee lookups
CREATE INDEX IF NOT EXISTS idx_auth_users_employee_id ON auth_users(employee_id);

-- Index on status for filtering active/inactive users
CREATE INDEX IF NOT EXISTS idx_auth_users_status ON auth_users(status);

-- Index on user_setup_id for linking to admin service
CREATE INDEX IF NOT EXISTS idx_auth_users_user_setup_id ON auth_users(user_setup_id);

-- ==================== STEP 6: CREATE TRIGGERS ====================

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Drop existing trigger if it exists
DROP TRIGGER IF EXISTS update_auth_users_updated_at ON auth_users;

-- Create trigger to update updated_at on every UPDATE
CREATE TRIGGER update_auth_users_updated_at
    BEFORE UPDATE ON auth_users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ==================== STEP 7: ADD COMMENTS ====================

COMMENT ON TABLE auth_users IS 'User authentication data synced from admin-service usersetup_basic table';
COMMENT ON COLUMN auth_users.id IS 'Primary key - matches usersetup_basic.id in admin-service';
COMMENT ON COLUMN auth_users.user_setup_id IS 'Reference to usersetup_basic.id in admin-service database';
COMMENT ON COLUMN auth_users.password_hash IS 'Bcrypt hashed password for authentication';
COMMENT ON COLUMN auth_users.is_password_change IS 'Flag indicating if user needs to change password on next login';
COMMENT ON COLUMN auth_users.tem_employee IS 'Flag indicating if this is a temporary employee';
COMMENT ON COLUMN auth_users.status IS 'User status: active, inactive, suspended, etc.';
COMMENT ON COLUMN auth_users.manage_roles IS 'Array of role UUIDs that this user can manage';
COMMENT ON COLUMN auth_users.entities IS 'Array of entity UUIDs that this user has access to';

-- ==================== STEP 8: GRANT PERMISSIONS ====================

-- Grant all privileges on the table to postgres user
GRANT ALL PRIVILEGES ON TABLE auth_users TO postgres;

-- Grant usage on sequences (for future use)
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO postgres;

-- ==================== VERIFICATION ====================

-- Show table structure
\d auth_users

-- Show all tables in database
\dt

-- Show all indexes
\di

-- Count rows (should be 0 for new installation)
SELECT COUNT(*) as total_users FROM auth_users;

-- ==================== COMPLETION MESSAGE ====================

DO $$
BEGIN
    RAISE NOTICE '============================================================';
    RAISE NOTICE 'Identity Database Setup Complete!';
    RAISE NOTICE '============================================================';
    RAISE NOTICE 'Database: auth_service';
    RAISE NOTICE 'Table: auth_users';
    RAISE NOTICE 'Status: Ready for sync';
    RAISE NOTICE '';
    RAISE NOTICE 'Next steps:';
    RAISE NOTICE '1. Configure IDENTITY_DATABASE_URL in your application';
    RAISE NOTICE '2. Restart admin-service';
    RAISE NOTICE '3. Create test user to verify sync';
    RAISE NOTICE '============================================================';
END $$;
