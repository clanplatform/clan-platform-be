-- Creates the entities_retail_ecommerce table — a branch's "Retail & store
-- operations" section (one row per entities row, carried in the branch payload
-- as the nested `entities_retail_ecommerce` list).
--
-- The table is defined by app/entities/models/entities_retail_ecommerce.py and
-- is created automatically in freshly provisioned tenant DBs (and at startup in
-- the master DB) via Base.metadata.create_all. This script provisions it for
-- databases that already exist. Run against:
--   1. The master DB (clan_platform)
--   2. EVERY existing tenant DB (clan_platform_<code>...)
--
-- Idempotent: CREATE TABLE / CREATE INDEX IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS entities_retail_ecommerce (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id           UUID NOT NULL REFERENCES entities(entity_id),
    tenant_id           UUID REFERENCES tenants(tenant_id),

    -- Retail & store operations
    store_format        VARCHAR(100),
    number_of_stores    INTEGER,
    pos_terminals       INTEGER,
    pos_system          VARCHAR(150),
    ecommerce_enabled   BOOLEAN NOT NULL DEFAULT false,
    loyalty_program     BOOLEAN NOT NULL DEFAULT false,

    active              BOOLEAN NOT NULL DEFAULT true,
    deleted             BOOLEAN NOT NULL DEFAULT false,
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_entities_retail_ecommerce_entity UNIQUE (entity_id)
);

CREATE INDEX IF NOT EXISTS ix_entities_retail_ecommerce_id ON entities_retail_ecommerce(id);
CREATE INDEX IF NOT EXISTS ix_entities_retail_ecommerce_entity_id ON entities_retail_ecommerce(entity_id);
CREATE INDEX IF NOT EXISTS ix_entities_retail_ecommerce_tenant_id ON entities_retail_ecommerce(tenant_id);
