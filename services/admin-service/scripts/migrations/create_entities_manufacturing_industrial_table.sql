-- Creates the entities_manufacturing_industrial table — a branch's
-- "Manufacturing plant & production" section (one row per entities row, carried
-- in the branch payload as the nested `entities_manufacturing_industrial` list).
--
-- The table is defined by
-- app/entities/models/entities_manufacturing_industrial.py and is created
-- automatically in freshly provisioned tenant DBs (and at startup in the master
-- DB) via Base.metadata.create_all. This script provisions it for databases
-- that already exist. Run against:
--   1. The master DB (clan_platform)
--   2. EVERY existing tenant DB (clan_platform_<code>...)
--
-- Idempotent: CREATE TABLE / CREATE INDEX IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS entities_manufacturing_industrial (
    id                           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id                    UUID NOT NULL REFERENCES entities(entity_id),
    tenant_id                    UUID REFERENCES tenants(tenant_id),

    -- Manufacturing compliance documents (file references / URLs)
    iso_certificates_doc         VARCHAR(500),
    safety_osha_compliance_doc   VARCHAR(500),
    environmental_permit_doc     VARCHAR(500),

    -- Manufacturing plant & production
    plant_type                   VARCHAR(100),
    production_lines             INTEGER,
    shift_pattern                VARCHAR(100),
    production_capacity          VARCHAR(100),
    iso_certifications           TEXT[],
    erp_mes_system               VARCHAR(150),
    handles_hazardous_materials  BOOLEAN NOT NULL DEFAULT false,
    unionized_workforce          BOOLEAN NOT NULL DEFAULT false,

    active                       BOOLEAN NOT NULL DEFAULT true,
    deleted                      BOOLEAN NOT NULL DEFAULT false,
    created_at                   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at                   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_entities_manufacturing_industrial_entity UNIQUE (entity_id)
);

CREATE INDEX IF NOT EXISTS ix_entities_manufacturing_industrial_id ON entities_manufacturing_industrial(id);
CREATE INDEX IF NOT EXISTS ix_entities_manufacturing_industrial_entity_id ON entities_manufacturing_industrial(entity_id);
CREATE INDEX IF NOT EXISTS ix_entities_manufacturing_industrial_tenant_id ON entities_manufacturing_industrial(tenant_id);
