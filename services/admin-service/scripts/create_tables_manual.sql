-- ================================================================
-- PostgreSQL Table Creation Script
-- Admin Service Database Schema
-- ================================================================
-- 
-- This script creates all tables for the Admin Service.
-- Execute this script in your PostgreSQL database.
--
-- Database: clan_platform
-- User: postgres
-- Password: root
--
-- Usage:
--   psql -h localhost -U postgres -d clan_platform -f create_tables_manual.sql
--
-- Or from Docker:
--   docker exec -i admin-service-postgres psql -U postgres -d clan_platform < create_tables_manual.sql
-- ================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ================================================================
-- 1. CLIENTS TABLE (No dependencies)
-- ================================================================
CREATE TABLE IF NOT EXISTS clients (
    client_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_name VARCHAR(255) NOT NULL,
    client_code VARCHAR(100),
    contact_email VARCHAR(255) NOT NULL,
    contact_phone VARCHAR(50),
    address VARCHAR(500),
    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100),
    industry VARCHAR(100),
    company_size VARCHAR(50),
    subscription_plan VARCHAR(100),
    onboarding_status VARCHAR(50),
    employees_count INTEGER,
    location VARCHAR(255),
    status VARCHAR(50),
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    deleted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    created_by UUID
);

CREATE INDEX IF NOT EXISTS idx_clients_client_id ON clients(client_id);
CREATE INDEX IF NOT EXISTS idx_clients_is_active ON clients(is_active);

-- ================================================================
-- 2. DOMAINS TABLE (No dependencies)
-- ================================================================
CREATE TABLE IF NOT EXISTS domains (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    domain_metadata JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_domains_code ON domains(code);
CREATE INDEX IF NOT EXISTS idx_domains_is_active ON domains(is_active);

-- ================================================================
-- 3. ENTITIES TABLE (Depends on: clients)
-- ================================================================
CREATE TABLE IF NOT EXISTS entities (
    entity_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID NOT NULL REFERENCES clients(client_id),
    entity_name VARCHAR(100) NOT NULL,
    entity_code VARCHAR(20) NOT NULL,
    company_size VARCHAR(50),
    description TEXT,
    contact VARCHAR(100),
    email VARCHAR(255),
    address_1 VARCHAR(200),
    address_2 VARCHAR(200),
    city_code VARCHAR(10),
    state_code VARCHAR(10),
    country_code VARCHAR(10),
    time_zone VARCHAR(50),
    time_zone_offset VARCHAR(10),
    date_format VARCHAR(20),
    time_format VARCHAR(20),
    date_time_format VARCHAR(40),
    active BOOLEAN DEFAULT TRUE NOT NULL,
    deleted BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_entities_entity_id ON entities(entity_id);
CREATE INDEX IF NOT EXISTS idx_entities_client_id ON entities(client_id);

-- ================================================================
-- 4. DEPARTMENTS TABLE (Depends on: clients, entities)
-- Note: manager_id and user-related FKs commented out (users table not in scope)
-- ================================================================
CREATE TABLE IF NOT EXISTS departments (
    department_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID NOT NULL REFERENCES clients(client_id),
    entity_id UUID REFERENCES entities(entity_id),
    parent_department_id UUID REFERENCES departments(department_id),
    department_name VARCHAR(100) NOT NULL,
    department_code VARCHAR(50),
    description TEXT,
    department_type VARCHAR(50),
    cost_center VARCHAR(50),
    budget_info JSONB DEFAULT '{}',
    -- manager_id UUID,  -- Commented: FK to users table
    location VARCHAR(255) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    email VARCHAR(255) NOT NULL,
    annual_budget NUMERIC(15, 2) NOT NULL,
    reporting_structure VARCHAR(100) NOT NULL,
    department_metadata JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_departments_client_id ON departments(client_id);
CREATE INDEX IF NOT EXISTS idx_departments_entity_id ON departments(entity_id);

-- ================================================================
-- 5. DIVISIONS TABLE (Depends on: clients, entities, departments)
-- ================================================================
CREATE TABLE IF NOT EXISTS divisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID NOT NULL REFERENCES clients(client_id),
    entity_id UUID REFERENCES entities(entity_id),
    division_name VARCHAR(100) NOT NULL,
    division_code VARCHAR(20) NOT NULL,
    department_id UUID REFERENCES departments(department_id),
    description TEXT,
    parent_division_id UUID REFERENCES divisions(id),
    hierarchy_level VARCHAR(10) DEFAULT '1',
    division_metadata JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    deleted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_divisions_client_id ON divisions(client_id);
CREATE INDEX IF NOT EXISTS idx_divisions_entity_id ON divisions(entity_id);
CREATE INDEX IF NOT EXISTS idx_divisions_department_id ON divisions(department_id);

-- ================================================================
-- 6. APPLICATIONS TABLE (Depends on: domains)
-- ================================================================
CREATE TABLE IF NOT EXISTS applications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    domain_id UUID NOT NULL REFERENCES domains(id),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    version VARCHAR(20) DEFAULT '1.0.0',
    status VARCHAR(50) DEFAULT 'active',
    config JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP WITH TIME ZONE,
    key VARCHAR(100),
    label VARCHAR(100),
    route VARCHAR(200),
    level INTEGER DEFAULT 1,
    icon VARCHAR(100),
    badge VARCHAR(50),
    section_title VARCHAR(200),
    access TEXT[],
    order_index INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_applications_domain_id ON applications(domain_id);
CREATE INDEX IF NOT EXISTS idx_applications_is_active ON applications(is_active);

-- ================================================================
-- 7. MODULES TABLE (Depends on: applications)
-- ================================================================
CREATE TABLE IF NOT EXISTS modules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(50) UNIQUE,
    key VARCHAR(100) UNIQUE,
    label VARCHAR(150),
    section_title VARCHAR(150),
    description TEXT,
    icon VARCHAR(100),
    badge VARCHAR(50),
    route VARCHAR(255),
    level INTEGER DEFAULT 2,
    order_index INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    is_deleted BOOLEAN DEFAULT FALSE,
    is_public BOOLEAN DEFAULT FALSE,
    access TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by INTEGER,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_by INTEGER
);

CREATE INDEX IF NOT EXISTS idx_modules_application_id ON modules(application_id);
CREATE INDEX IF NOT EXISTS idx_modules_code ON modules(code);

-- ================================================================
-- 8. MENUS TABLE (Depends on: applications, modules)
-- ================================================================
CREATE TABLE IF NOT EXISTS menus (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID NOT NULL REFERENCES applications(id),
    module_id UUID REFERENCES modules(id),
    mongo_id VARCHAR(24),
    name VARCHAR(100) NOT NULL,
    label VARCHAR(100) NOT NULL,
    icon VARCHAR(50),
    route VARCHAR(200),
    component VARCHAR(100),
    order_index INTEGER DEFAULT 0,
    level INTEGER DEFAULT 3,
    is_visible BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,
    deleted_at TIMESTAMP WITH TIME ZONE,
    menu_metadata JSONB DEFAULT '{}',
    showtopbar BOOLEAN DEFAULT TRUE,
    showsidebar BOOLEAN DEFAULT TRUE,
    key VARCHAR(100),
    badge JSONB,
    section_title VARCHAR(200),
    menus_description TEXT,
    parent_menu_id UUID REFERENCES menus(id),
    access TEXT[] NOT NULL DEFAULT ARRAY['read']::TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_menus_application_id ON menus(application_id);
CREATE INDEX IF NOT EXISTS idx_menus_module_id ON menus(module_id);
CREATE INDEX IF NOT EXISTS idx_menus_mongo_id ON menus(mongo_id);
CREATE INDEX IF NOT EXISTS idx_menus_parent_menu_id ON menus(parent_menu_id);

-- ================================================================
-- 9. FORMS TABLE (Depends on: menus)
-- ================================================================
CREATE TABLE IF NOT EXISTS forms (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    menu_id UUID NOT NULL REFERENCES menus(id) ON DELETE CASCADE,
    mongo_id VARCHAR(24),
    name VARCHAR(100) NOT NULL,
    version VARCHAR(20) DEFAULT '1.0.0',
    trigger_when VARCHAR(255),
    forms JSONB NOT NULL,
    actions JSONB DEFAULT '{}',
    access TEXT[] NOT NULL DEFAULT ARRAY['read']::TEXT[],
    modal_type VARCHAR(50) DEFAULT 'AntModalAdapter',
    tooltip_type VARCHAR(50) DEFAULT 'AntTooltip',
    error_type VARCHAR(50) DEFAULT 'AntErrorMessage',
    localization JSONB DEFAULT '{}',
    languages JSONB DEFAULT '[]',
    default_language VARCHAR(10) DEFAULT 'en-US',
    is_active BOOLEAN DEFAULT TRUE,
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(50),
    updated_by VARCHAR(50)
);

CREATE INDEX IF NOT EXISTS idx_forms_menu_id ON forms(menu_id);
CREATE INDEX IF NOT EXISTS idx_forms_mongo_id ON forms(mongo_id);

-- ================================================================
-- 10. JOB CODES TABLE (No dependencies)
-- ================================================================
CREATE TABLE IF NOT EXISTS job_codes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_code VARCHAR(50) UNIQUE NOT NULL,
    job_title VARCHAR(150) NOT NULL,
    active_status BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_job_codes_id ON job_codes(id);
CREATE INDEX IF NOT EXISTS idx_job_codes_job_code ON job_codes(job_code);
CREATE INDEX IF NOT EXISTS idx_job_codes_active_status ON job_codes(active_status);
CREATE INDEX IF NOT EXISTS idx_job_codes_job_title ON job_codes(job_title);
CREATE INDEX IF NOT EXISTS idx_job_codes_created_at ON job_codes(created_at);
CREATE INDEX IF NOT EXISTS idx_job_codes_composite_search ON job_codes(job_code, job_title, active_status);

-- ================================================================
-- 11. JOB CODE BASIC INFO TABLE (Depends on: job_codes, clients, entities, departments, divisions)
-- ================================================================
CREATE TABLE IF NOT EXISTS jobcode_basicinfo (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_code_id UUID UNIQUE NOT NULL REFERENCES job_codes(id) ON DELETE CASCADE,
    category VARCHAR(100),
    level VARCHAR(50),
    description TEXT,
    client_id UUID NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    entity_id UUID NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    department_id UUID NOT NULL REFERENCES departments(department_id) ON DELETE CASCADE,
    division_id UUID NOT NULL REFERENCES divisions(id) ON DELETE CASCADE,
    employment_type VARCHAR(50),
    work_mode VARCHAR(50),
    minimum_salary INTEGER,
    maximum_salary INTEGER,
    experience_years INTEGER,
    reports_to VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobcode_basicinfo_id ON jobcode_basicinfo(id);
CREATE INDEX IF NOT EXISTS idx_jobcode_basicinfo_job_code_id ON jobcode_basicinfo(job_code_id);
CREATE INDEX IF NOT EXISTS idx_jobcode_basicinfo_client_id ON jobcode_basicinfo(client_id);
CREATE INDEX IF NOT EXISTS idx_jobcode_basicinfo_entity_id ON jobcode_basicinfo(entity_id);
CREATE INDEX IF NOT EXISTS idx_jobcode_basicinfo_department_id ON jobcode_basicinfo(department_id);
CREATE INDEX IF NOT EXISTS idx_jobcode_basicinfo_division_id ON jobcode_basicinfo(division_id);
CREATE INDEX IF NOT EXISTS idx_jobcode_basicinfo_category_level ON jobcode_basicinfo(category, level);
CREATE INDEX IF NOT EXISTS idx_jobcode_basicinfo_department_division ON jobcode_basicinfo(department_id, division_id);
CREATE INDEX IF NOT EXISTS idx_jobcode_basicinfo_employment_work ON jobcode_basicinfo(employment_type, work_mode);

-- ================================================================
-- 12. JOB CODE SKILLS TABLE (Depends on: job_codes)
-- ================================================================
CREATE TABLE IF NOT EXISTS jobcode_skills (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_code_id UUID UNIQUE NOT NULL REFERENCES job_codes(id) ON DELETE CASCADE,
    key_responsibilities TEXT,
    requirements TEXT,
    required_skills TEXT,
    education_level VARCHAR(100),
    certifications TEXT,
    performance_metrics TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobcode_skills_id ON jobcode_skills(id);
CREATE INDEX IF NOT EXISTS idx_jobcode_skills_job_code_id ON jobcode_skills(job_code_id);
CREATE INDEX IF NOT EXISTS idx_jobcode_skills_education_level ON jobcode_skills(education_level);

-- ================================================================
-- 13. JOB CODE BENEFITS TABLE (Depends on: job_codes)
-- ================================================================
CREATE TABLE IF NOT EXISTS jobcode_benefits (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_code_id UUID UNIQUE NOT NULL REFERENCES job_codes(id) ON DELETE CASCADE,
    benefits_package TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobcode_benefits_id ON jobcode_benefits(id);
CREATE INDEX IF NOT EXISTS idx_jobcode_benefits_job_code_id ON jobcode_benefits(job_code_id);

-- ================================================================
-- 14. AUDIT LOGS TABLE (Depends on: clients, entities)
-- Note: user_id FK commented out (users table not in scope)
-- ================================================================
CREATE TABLE IF NOT EXISTS audit_logs (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    -- user_id UUID,  -- Commented: FK to users table
    client_id UUID NOT NULL REFERENCES clients(client_id),
    entity_id UUID REFERENCES entities(entity_id),
    action VARCHAR(100) NOT NULL,
    object_type VARCHAR(100) NOT NULL,
    object_id VARCHAR(255),
    old_values JSONB DEFAULT '{}',
    new_values JSONB DEFAULT '{}',
    ip_address VARCHAR(45),
    user_agent TEXT,
    session_id VARCHAR(255),
    risk_score VARCHAR(20),
    compliance_tags JSONB DEFAULT '[]',
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_client_id ON audit_logs(client_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_entity_id ON audit_logs(entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp);

-- ================================================================
-- End of Script
-- ================================================================

-- Verify table creation
SELECT 
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) AS column_count
FROM information_schema.tables t
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
ORDER BY table_name;
