-- Creates the entities_banking_financial table — a branch's "Financial services
-- & regulation" section (one row per entities row, carried in the branch
-- payload as the nested `entities_banking_financial` list).
--
-- The table is defined by app/entities/models/entities_banking_financial.py and
-- is created automatically in freshly provisioned tenant DBs (and at startup in
-- the master DB) via Base.metadata.create_all. This script provisions it for
-- databases that already exist. Run against:
--   1. The master DB (clan_platform)
--   2. EVERY existing tenant DB (clan_platform_<code>...)
--
-- Idempotent: CREATE TABLE / CREATE INDEX IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS entities_banking_financial (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id                UUID NOT NULL REFERENCES entities(entity_id),
    tenant_id                UUID REFERENCES tenants(tenant_id),

    -- Financial services compliance documents (file references / URLs)
    regulatory_license_doc   VARCHAR(500),
    aml_kyc_policy_doc        VARCHAR(500),
    pci_dss_attestation_doc   VARCHAR(500),

    -- Financial services & regulation
    primary_regulator        VARCHAR(100),
    license_type             VARCHAR(100),
    license_number           VARCHAR(100),
    aml_compliance_officer    VARCHAR(200),
    kyc_level                VARCHAR(50),
    pci_dss_in_scope         BOOLEAN NOT NULL DEFAULT false,

    active                   BOOLEAN NOT NULL DEFAULT true,
    deleted                  BOOLEAN NOT NULL DEFAULT false,
    created_at               TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_entities_banking_financial_entity UNIQUE (entity_id)
);

CREATE INDEX IF NOT EXISTS ix_entities_banking_financial_id ON entities_banking_financial(id);
CREATE INDEX IF NOT EXISTS ix_entities_banking_financial_entity_id ON entities_banking_financial(entity_id);
CREATE INDEX IF NOT EXISTS ix_entities_banking_financial_tenant_id ON entities_banking_financial(tenant_id);
