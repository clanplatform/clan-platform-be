-- Creates the entities_education table — a branch's "Education institution"
-- section (one row per entities row, carried in the branch payload as the nested
-- `entities_education` list).
--
-- The table is defined by app/entities/models/entities_education.py and is
-- created automatically in freshly provisioned tenant DBs (and at startup in the
-- master DB) via Base.metadata.create_all. This script provisions it for
-- databases that already exist. Run against:
--   1. The master DB (clan_platform)
--   2. EVERY existing tenant DB (clan_platform_<code>...)
--
-- Idempotent: CREATE TABLE / CREATE INDEX IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS entities_education (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id           UUID NOT NULL REFERENCES entities(entity_id),
    tenant_id           UUID REFERENCES tenants(tenant_id),

    -- Education institution
    institution_type    VARCHAR(100),
    students_enrolled   INTEGER,
    campuses            INTEGER,
    accreditation_body  VARCHAR(100),

    active              BOOLEAN NOT NULL DEFAULT true,
    deleted             BOOLEAN NOT NULL DEFAULT false,
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_entities_education_entity UNIQUE (entity_id)
);

CREATE INDEX IF NOT EXISTS ix_entities_education_id ON entities_education(id);
CREATE INDEX IF NOT EXISTS ix_entities_education_entity_id ON entities_education(entity_id);
CREATE INDEX IF NOT EXISTS ix_entities_education_tenant_id ON entities_education(tenant_id);
