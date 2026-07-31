-- Extends the entities (branches) table with the extra fields from the
-- onboarding "Add branch" form. Existing columns (entity_name, entity_code,
-- company_size, contact, email, address_1/2, city_code, state_code,
-- country_code, time_zone) are unchanged.
--
-- Added:
--   Branch profile     : location_type, is_headquarters, phone,
--                        tax_registration, postal_code
--   Operating schedule : working_days, business_hours_start,
--                        business_hours_end, observes_dst
--   Compliance docs    : business_registration_doc, tax_certificate_doc,
--                        incorporation_certificate_doc,
--                        data_processing_agreement_doc,
--                        insurance_certificate_doc, other_documents_doc
--
-- entities lives in every tenant DB (and the master DB), so run against:
--   1. The master DB (clan_platform)
--   2. EVERY existing tenant DB (clan_platform_<code>...)
-- New tenant DBs provisioned after this change get the columns from the models.
--
-- Idempotent: ADD COLUMN IF NOT EXISTS, and ALTER TABLE IF EXISTS skips
-- databases without the table.

-- Branch profile
ALTER TABLE IF EXISTS entities ADD COLUMN IF NOT EXISTS location_type    VARCHAR(50);
ALTER TABLE IF EXISTS entities ADD COLUMN IF NOT EXISTS is_headquarters  BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE IF EXISTS entities ADD COLUMN IF NOT EXISTS phone            VARCHAR(20);
ALTER TABLE IF EXISTS entities ADD COLUMN IF NOT EXISTS tax_registration VARCHAR(100);
ALTER TABLE IF EXISTS entities ADD COLUMN IF NOT EXISTS postal_code      VARCHAR(20);

-- Operating schedule (defaults)
ALTER TABLE IF EXISTS entities ADD COLUMN IF NOT EXISTS working_days         VARCHAR(100);
ALTER TABLE IF EXISTS entities ADD COLUMN IF NOT EXISTS business_hours_start VARCHAR(10);
ALTER TABLE IF EXISTS entities ADD COLUMN IF NOT EXISTS business_hours_end   VARCHAR(10);
ALTER TABLE IF EXISTS entities ADD COLUMN IF NOT EXISTS observes_dst         BOOLEAN NOT NULL DEFAULT false;

-- Compliance & documents (stored file references / URLs)
ALTER TABLE IF EXISTS entities ADD COLUMN IF NOT EXISTS business_registration_doc     VARCHAR(500);
ALTER TABLE IF EXISTS entities ADD COLUMN IF NOT EXISTS tax_certificate_doc           VARCHAR(500);
ALTER TABLE IF EXISTS entities ADD COLUMN IF NOT EXISTS incorporation_certificate_doc VARCHAR(500);
ALTER TABLE IF EXISTS entities ADD COLUMN IF NOT EXISTS data_processing_agreement_doc VARCHAR(500);
ALTER TABLE IF EXISTS entities ADD COLUMN IF NOT EXISTS insurance_certificate_doc     VARCHAR(500);
ALTER TABLE IF EXISTS entities ADD COLUMN IF NOT EXISTS other_documents_doc           VARCHAR(500);
