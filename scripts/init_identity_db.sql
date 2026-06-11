-- ============================================================
-- Identity Database Initialization Script
-- Creates auth_users table for user authentication sync
-- ============================================================

-- Create UUID extension if not exists
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Drop table if exists (for development only)
-- DROP TABLE IF EXISTS auth_users CASCADE;

-- Create auth_users table
CREATE TABLE IF NOT EXISTS auth_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_setup_id UUID,  -- Reference to usersetup_basic.id in admin-service
    firstname VARCHAR(100) NOT NULL,
    lastname VARCHAR(100) NOT NULL,
    employee_id VARCHAR(50) NOT NULL UNIQUE,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    phone_number VARCHAR(20),
    password_hash VARCHAR(255) NOT NULL,
    password_changed TIMESTAMP WITH TIME ZONE,
    is_password_change BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    start_date DATE,
    end_date DATE,
    tem_employee BOOLEAN NOT NULL DEFAULT FALSE,
    department UUID,
    division UUID,
    job_code UUID,
    manage_roles UUID[],
    default_dept UUID,
    reporting_to UUID,
    entities UUID[],
    default_entity UUID,
    view VARCHAR(50),
    dashboard_view VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_auth_users_username ON auth_users(username);
CREATE INDEX IF NOT EXISTS idx_auth_users_email ON auth_users(email);
CREATE INDEX IF NOT EXISTS idx_auth_users_employee_id ON auth_users(employee_id);
CREATE INDEX IF NOT EXISTS idx_auth_users_status ON auth_users(status);
CREATE INDEX IF NOT EXISTS idx_auth_users_user_setup_id ON auth_users(user_setup_id);

-- Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_auth_users_updated_at ON auth_users;
CREATE TRIGGER update_auth_users_updated_at
    BEFORE UPDATE ON auth_users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions (adjust based on your database user)
-- GRANT ALL PRIVILEGES ON TABLE auth_users TO postgres;

COMMENT ON TABLE auth_users IS 'User authentication data synced from admin-service usersetup_basic table';
COMMENT ON COLUMN auth_users.user_setup_id IS 'Reference to usersetup_basic.id in admin-service database';
COMMENT ON COLUMN auth_users.password_hash IS 'Bcrypt hashed password';
COMMENT ON COLUMN auth_users.is_password_change IS 'Flag indicating if user needs to change password on next login';
COMMENT ON COLUMN auth_users.tem_employee IS 'Flag indicating if this is a temporary employee';
