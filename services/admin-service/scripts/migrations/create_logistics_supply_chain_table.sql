-- Creates the logistics_supply_chain table — a branch's "Logistics & supply
-- chain" section (one row per entities row, carried in the branch payload as the
-- nested `logistics_supply_chain` list).
--
-- The table is defined by app/entities/models/logistics_supply_chain.py and is
-- created automatically in freshly provisioned tenant DBs (and at startup in the
-- master DB) via Base.metadata.create_all. This script provisions it for
-- databases that already exist. Run against:
--   1. The master DB (clan_platform)
--   2. EVERY existing tenant DB (clan_platform_<code>...)
--
-- Idempotent: CREATE TABLE / CREATE INDEX IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS logistics_supply_chain (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id         UUID NOT NULL REFERENCES entities(entity_id),
    tenant_id         UUID REFERENCES tenants(tenant_id),

    -- Logistics & supply chain
    fleet_size        VARCHAR(100),
    warehouses_dcs    INTEGER,
    transport_modes   TEXT[],
    wms_tms_system    VARCHAR(150),

    active            BOOLEAN NOT NULL DEFAULT true,
    deleted           BOOLEAN NOT NULL DEFAULT false,
    created_at        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_logistics_supply_chain_entity UNIQUE (entity_id)
);

CREATE INDEX IF NOT EXISTS ix_logistics_supply_chain_id ON logistics_supply_chain(id);
CREATE INDEX IF NOT EXISTS ix_logistics_supply_chain_entity_id ON logistics_supply_chain(entity_id);
CREATE INDEX IF NOT EXISTS ix_logistics_supply_chain_tenant_id ON logistics_supply_chain(tenant_id);
