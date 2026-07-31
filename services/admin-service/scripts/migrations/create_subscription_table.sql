-- Creates the subscription table — a tenant's plan, application/module grants
-- and add-on limits (the onboarding "Subscription plan" step).
--
-- The table is defined by app/subscription/models/subscription.py and is created
-- automatically in freshly provisioned tenant DBs (and at startup in the master
-- DB) via Base.metadata.create_all. This script provisions it for databases that
-- already exist. Run against:
--   1. The master DB (clan_platform)
--   2. EVERY existing tenant DB (clan_platform_<code>...)
--
-- Idempotent: CREATE TABLE / CREATE INDEX IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS subscription (
    subscription_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id             UUID REFERENCES tenants(tenant_id),

    -- Subscription plan
    plan                  VARCHAR(50),          -- Standard | Professional | Enterprise
    billing_cycle         VARCHAR(20),          -- Annual | Monthly | Quarterly
    licensed_user_seats   INTEGER,
    start_as_trial        BOOLEAN NOT NULL DEFAULT false,

    -- Grants (platform application / module ids)
    applications_to_grant UUID[],
    modules_to_grant      UUID[],

    -- Add-ons & limits
    extra_storage         VARCHAR(50),          -- None | 50GB | 100GB | ...
    support_tier          VARCHAR(50),
    api_access            BOOLEAN NOT NULL DEFAULT false,
    sandbox_environment   BOOLEAN NOT NULL DEFAULT false,
    white_label_branding  BOOLEAN NOT NULL DEFAULT false,

    is_active             BOOLEAN NOT NULL DEFAULT true,
    created_at            TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by            UUID
);

CREATE INDEX IF NOT EXISTS ix_subscription_tenant_id ON subscription(tenant_id);
CREATE INDEX IF NOT EXISTS ix_subscription_subscription_id ON subscription(subscription_id);
