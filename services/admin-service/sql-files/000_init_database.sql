-- ================================================
-- Migration: 000_init_database.sql
-- Description: Initial database setup and extensions
-- Author: Admin Service Team
-- Date: 2024
-- ================================================

-- Enable required PostgreSQL extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fuzzy text search
CREATE EXTENSION IF NOT EXISTS "btree_gin"; -- For GIN indexes on btree types

-- Set default timezone
SET timezone = 'UTC';

-- Create schema if needed (optional, comment out if using default 'public' schema)
-- CREATE SCHEMA IF NOT EXISTS admin_service;
-- SET search_path TO admin_service, public;

-- Display database info
SELECT 
    current_database() as database,
    current_user as user,
    version() as postgres_version;

RAISE NOTICE 'Database initialized successfully';
