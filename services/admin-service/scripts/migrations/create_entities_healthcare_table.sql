-- Creates the entities_healthcare table — a branch's "Healthcare facility &
-- compliance" section (one row per entities row, carried in the branch payload
-- as the nested `entities_healthcare` list).
--
-- The table is defined by app/entities/models/entities_healthcare.py and is
-- created automatically in freshly provisioned tenant DBs (and at startup in
-- the master DB) via Base.metadata.create_all. This script provisions it for
-- databases that already exist. Run against:
--   1. The master DB (clan_platform)
--   2. EVERY existing tenant DB (clan_platform_<code>...)
--
-- Idempotent: CREATE TABLE / CREATE INDEX IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS entities_healthcare (
    id                                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id                         UUID NOT NULL REFERENCES entities(entity_id),
    tenant_id                         UUID REFERENCES tenants(tenant_id),

    -- Healthcare compliance documents (file references / URLs)
    facility_license_doc              VARCHAR(500),
    accreditation_certificate_doc     VARCHAR(500),
    dea_registration_doc              VARCHAR(500),
    hipaa_compliance_attestation_doc  VARCHAR(500),

    -- Healthcare facility & compliance
    facility_type                     VARCHAR(100),
    npi_number                        VARCHAR(50),
    facility_license_no               VARCHAR(100),
    license_expiry                    DATE,
    accreditation                     VARCHAR(100),
    bed_capacity                      INTEGER,
    licensed_practitioners            INTEGER,
    ehr_emr_system                    VARCHAR(150),
    hipaa_privacy_officer             VARCHAR(200),
    officer_email                     VARCHAR(255),
    telehealth_enabled                BOOLEAN NOT NULL DEFAULT false,
    handles_phi                       BOOLEAN NOT NULL DEFAULT false,

    active                            BOOLEAN NOT NULL DEFAULT true,
    deleted                           BOOLEAN NOT NULL DEFAULT false,
    created_at                        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at                        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_entities_healthcare_entity UNIQUE (entity_id)
);

CREATE INDEX IF NOT EXISTS ix_entities_healthcare_id ON entities_healthcare(id);
CREATE INDEX IF NOT EXISTS ix_entities_healthcare_entity_id ON entities_healthcare(entity_id);
CREATE INDEX IF NOT EXISTS ix_entities_healthcare_tenant_id ON entities_healthcare(tenant_id);
