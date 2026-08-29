-- Wires the branch-form per-vertical compliance sections to the tenant's
-- industry vertical.
--
--   * domains.branch_compliance_key  (new, nullable) — the branches[] nested
--     key / table name a vertical unlocks (e.g. 'entities_healthcare').
--   * tenants.primary_domain (String)  ->  tenants.primary_domain_id (UUID FK
--     -> domains.id).
--
-- Models: app/domains/models/domain.py, app/tenants/models/tenants.py.
-- Freshly provisioned tenant DBs get this shape from create_all(). Run this
-- against databases that already exist:
--   1. The master DB (clan_platform)
--   2. EVERY existing tenant DB (clan_platform_<code>...)
--
-- Idempotent: ADD COLUMN IF NOT EXISTS + guarded backfills.

-- 1. domains.branch_compliance_key ------------------------------------------
ALTER TABLE domains ADD COLUMN IF NOT EXISTS branch_compliance_key VARCHAR(64);
CREATE INDEX IF NOT EXISTS ix_domains_branch_compliance_key ON domains(branch_compliance_key);

-- 2. seed the 6 verticals that have a compliance table (fill NULLs only) -----
UPDATE domains SET branch_compliance_key = 'entities_healthcare'                WHERE code = 'HEALTHCARE_LIFE_SCIENCES'   AND branch_compliance_key IS NULL;
UPDATE domains SET branch_compliance_key = 'entities_manufacturing_industrial' WHERE code = 'MANUFACTURING_INDUSTRIAL'   AND branch_compliance_key IS NULL;
UPDATE domains SET branch_compliance_key = 'entities_retail_ecommerce'         WHERE code = 'RETAIL_ECOMMERCE'           AND branch_compliance_key IS NULL;
UPDATE domains SET branch_compliance_key = 'entities_banking_financial'        WHERE code = 'BANKING_FINANCIAL_SERVICES' AND branch_compliance_key IS NULL;
UPDATE domains SET branch_compliance_key = 'logistics_supply_chain'           WHERE code = 'LOGISTICS_SUPPLY_CHAIN'      AND branch_compliance_key IS NULL;
UPDATE domains SET branch_compliance_key = 'entities_education'                WHERE code = 'EDUCATION'                   AND branch_compliance_key IS NULL;

-- 3. tenants.primary_domain_id --------------------------------------------------
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS primary_domain_id UUID;
CREATE INDEX IF NOT EXISTS ix_tenants_primary_domain_id ON tenants(primary_domain_id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_tenants_primary_domain_id_domains'
          AND table_name = 'tenants'
    ) THEN
        ALTER TABLE tenants
            ADD CONSTRAINT fk_tenants_primary_domain_id_domains
            FOREIGN KEY (primary_domain_id) REFERENCES domains(id);
    END IF;
END $$;

-- 4. best-effort backfill from the legacy primary_domain string ---------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'tenants' AND column_name = 'primary_domain'
    ) THEN
        UPDATE tenants t
           SET primary_domain_id = d.id
          FROM domains d
         WHERE t.primary_domain_id IS NULL
           AND t.primary_domain IS NOT NULL
           AND lower(regexp_replace(t.primary_domain, '[^a-z0-9]', '', 'gi')) IN (
                 lower(regexp_replace(d.code, '[^a-z0-9]', '', 'gi')),
                 lower(regexp_replace(d.name, '[^a-z0-9]', '', 'gi')));
    END IF;
END $$;

-- 5. drop the legacy column --------------------------------------------------
ALTER TABLE tenants DROP COLUMN IF EXISTS primary_domain;
