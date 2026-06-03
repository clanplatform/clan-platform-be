-- ================================================
-- Rollback: 999_rollback_all.sql
-- Description: Rollback all migrations (USE WITH CAUTION!)
-- Author: Admin Service Team
-- Date: 2024
-- WARNING: This will delete all tables and data!
-- ================================================

-- Drop tables in reverse order (respecting foreign key constraints)
DROP TABLE IF EXISTS menus CASCADE;
DROP TABLE IF EXISTS applications CASCADE;
DROP TABLE IF EXISTS domains CASCADE;

-- Drop trigger function
DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;

-- Optionally drop extensions (comment out if shared with other services)
-- DROP EXTENSION IF EXISTS "uuid-ossp";
-- DROP EXTENSION IF EXISTS "pg_trgm";
-- DROP EXTENSION IF EXISTS "btree_gin";

RAISE NOTICE 'All tables and functions have been dropped';
