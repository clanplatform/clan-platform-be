-- Extends the tenants table with the richer client-profile fields from the
-- onboarding step-1 form, and drops two redundant columns.
--
-- Added (all nullable):
--   Company identity : display_name, registration_number, tax_id, founded_year,
--                      website, annual_revenue
--   HQ address       : postal_code
--   Primary contact  : contact_name, contact_title
--   Domain & model   : primary_domain, business_model, organization_type
--   Localization     : default_language, timezone, default_currency,
--                      date_format, fiscal_year_start, week_starts_on
--   Account status   : internal_notes
-- Kept: is_active, address, description.
-- Dropped: status (use is_active), location (use address / city / state / country),
--          subscription_plan (removed by request; was cross-service sync metadata).
--
-- The tenants table lives in the master DB and is copied into every tenant DB,
-- so run against:
--   1. The master DB (clan_platform)
--   2. EVERY existing tenant DB (clan_platform_<code>...)
-- New tenant DBs provisioned after this change get the columns from the models.
--
-- Idempotent: ADD COLUMN IF NOT EXISTS / DROP COLUMN IF EXISTS, and
-- ALTER TABLE IF EXISTS skips databases without the table.

-- Company identity
ALTER TABLE IF EXISTS tenants ADD COLUMN IF NOT EXISTS display_name        VARCHAR(255);
ALTER TABLE IF EXISTS tenants ADD COLUMN IF NOT EXISTS registration_number VARCHAR(100);
ALTER TABLE IF EXISTS tenants ADD COLUMN IF NOT EXISTS tax_id              VARCHAR(100);
ALTER TABLE IF EXISTS tenants ADD COLUMN IF NOT EXISTS founded_year        INTEGER;
ALTER TABLE IF EXISTS tenants ADD COLUMN IF NOT EXISTS website             VARCHAR(255);
ALTER TABLE IF EXISTS tenants ADD COLUMN IF NOT EXISTS annual_revenue      VARCHAR(100);

-- Headquarters address
ALTER TABLE IF EXISTS tenants ADD COLUMN IF NOT EXISTS postal_code         VARCHAR(20);

-- Primary contact
ALTER TABLE IF EXISTS tenants ADD COLUMN IF NOT EXISTS contact_name        VARCHAR(255);
ALTER TABLE IF EXISTS tenants ADD COLUMN IF NOT EXISTS contact_title       VARCHAR(100);

-- Business domain & model
ALTER TABLE IF EXISTS tenants ADD COLUMN IF NOT EXISTS primary_domain      VARCHAR(100);
ALTER TABLE IF EXISTS tenants ADD COLUMN IF NOT EXISTS business_model      VARCHAR(100);
ALTER TABLE IF EXISTS tenants ADD COLUMN IF NOT EXISTS organization_type   VARCHAR(100);

-- Localization & business defaults
ALTER TABLE IF EXISTS tenants ADD COLUMN IF NOT EXISTS default_language    VARCHAR(50);
ALTER TABLE IF EXISTS tenants ADD COLUMN IF NOT EXISTS timezone            VARCHAR(50);
ALTER TABLE IF EXISTS tenants ADD COLUMN IF NOT EXISTS default_currency    VARCHAR(10);
ALTER TABLE IF EXISTS tenants ADD COLUMN IF NOT EXISTS date_format         VARCHAR(20);
ALTER TABLE IF EXISTS tenants ADD COLUMN IF NOT EXISTS fiscal_year_start   VARCHAR(20);
ALTER TABLE IF EXISTS tenants ADD COLUMN IF NOT EXISTS week_starts_on      VARCHAR(20);

-- Account status
ALTER TABLE IF EXISTS tenants ADD COLUMN IF NOT EXISTS internal_notes      TEXT;

-- Drop removed columns
ALTER TABLE IF EXISTS tenants DROP COLUMN IF EXISTS status;
ALTER TABLE IF EXISTS tenants DROP COLUMN IF EXISTS location;
ALTER TABLE IF EXISTS tenants DROP COLUMN IF EXISTS subscription_plan;
