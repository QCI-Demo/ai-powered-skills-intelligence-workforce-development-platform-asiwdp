-- =============================================================================
-- ASIWDP Tenant Provisioning Schema - PostgreSQL DDL
-- Story: Build Automated Tenant Provisioning and Configuration Service
-- Task: 89d8dbba-19a6-4a35-8382-d1be49c1fcf0
-- =============================================================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- Enum Types
-- =============================================================================

CREATE TYPE tenant_status AS ENUM (
    'provisioning',
    'active',
    'suspended',
    'deprovisioning',
    'deleted'
);

CREATE TYPE tenant_tier AS ENUM (
    'free',
    'standard',
    'professional',
    'enterprise'
);

CREATE TYPE event_delivery_status AS ENUM (
    'pending',
    'delivered',
    'failed',
    'retry'
);

-- =============================================================================
-- Table: tenants
-- Core tenant entity with partition key tenant_id
-- =============================================================================

CREATE TABLE tenants (
    tenant_id       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(255) NOT NULL,
    slug            VARCHAR(100) NOT NULL,
    display_name    VARCHAR(255),
    status          tenant_status NOT NULL DEFAULT 'provisioning',
    tier            tenant_tier NOT NULL DEFAULT 'standard',
    owner_user_id   UUID,
    contact_email   VARCHAR(255) NOT NULL,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    provisioned_at  TIMESTAMPTZ,
    provisioned_by  UUID,
    
    CONSTRAINT uq_tenants_name UNIQUE (name),
    CONSTRAINT uq_tenants_slug UNIQUE (slug),
    CONSTRAINT chk_tenants_email CHECK (contact_email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
    CONSTRAINT chk_tenants_slug CHECK (slug ~* '^[a-z0-9][a-z0-9-]*[a-z0-9]$' AND LENGTH(slug) >= 3)
);

COMMENT ON TABLE tenants IS 'Core tenant entity for multi-tenant isolation';
COMMENT ON COLUMN tenants.tenant_id IS 'Primary partition key for tenant isolation';
COMMENT ON COLUMN tenants.slug IS 'URL-safe unique identifier for the tenant';
COMMENT ON COLUMN tenants.status IS 'Lifecycle status: provisioning → active → suspended → deprovisioning → deleted';
COMMENT ON COLUMN tenants.tier IS 'Subscription tier determining feature limits';
COMMENT ON COLUMN tenants.metadata IS 'Extensible JSONB attributes for custom data';

-- =============================================================================
-- Table: tenant_configurations
-- Tenant-scoped configuration with defaults
-- =============================================================================

CREATE TABLE tenant_configurations (
    config_id       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    config_key      VARCHAR(255) NOT NULL,
    config_value    JSONB NOT NULL,
    is_default      BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT uq_tenant_config_key UNIQUE (tenant_id, config_key)
);

COMMENT ON TABLE tenant_configurations IS 'Tenant-scoped configuration settings';
COMMENT ON COLUMN tenant_configurations.config_key IS 'Configuration key (e.g., features.skills_intelligence)';
COMMENT ON COLUMN tenant_configurations.is_default IS 'True if using platform default, false if customized';

-- =============================================================================
-- Table: tenant_metadata
-- Extensible key-value metadata with scope
-- =============================================================================

CREATE TABLE tenant_metadata (
    metadata_id     UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    key             VARCHAR(255) NOT NULL,
    value           JSONB NOT NULL,
    scope           VARCHAR(100) NOT NULL DEFAULT 'general',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT uq_tenant_metadata_key_scope UNIQUE (tenant_id, key, scope)
);

COMMENT ON TABLE tenant_metadata IS 'Extensible tenant-scoped metadata storage';
COMMENT ON COLUMN tenant_metadata.scope IS 'Category/scope for metadata (e.g., billing, compliance, integrations)';

-- =============================================================================
-- Table: idempotency_keys
-- Idempotency tracking for tenant provisioning requests
-- =============================================================================

CREATE TABLE idempotency_keys (
    idempotency_key VARCHAR(255) PRIMARY KEY,
    tenant_id       UUID,
    request_hash    VARCHAR(64) NOT NULL,
    response        JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL,
    
    CONSTRAINT chk_idempotency_expires CHECK (expires_at > created_at)
);

COMMENT ON TABLE idempotency_keys IS 'Tracks idempotency keys for replay protection';
COMMENT ON COLUMN idempotency_keys.request_hash IS 'SHA-256 hash of the original request body';
COMMENT ON COLUMN idempotency_keys.expires_at IS 'TTL after which the key can be cleaned up (default 24h)';

-- =============================================================================
-- Table: tenant_provisioning_events
-- Audit log for provisioning events (telemetry)
-- =============================================================================

CREATE TABLE tenant_provisioning_events (
    event_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    event_type      VARCHAR(100) NOT NULL,
    payload         JSONB NOT NULL,
    emitted_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status          event_delivery_status NOT NULL DEFAULT 'pending',
    
    CONSTRAINT chk_event_type CHECK (event_type IN (
        'tenant.provisioning.started',
        'tenant.provisioning.completed',
        'tenant.provisioning.failed',
        'tenant.configuration.initialized',
        'tenant.status.changed',
        'tenant.tier.changed'
    ))
);

COMMENT ON TABLE tenant_provisioning_events IS 'Audit trail and telemetry for provisioning events';
COMMENT ON COLUMN tenant_provisioning_events.status IS 'Event delivery status to event bus';

-- =============================================================================
-- Indexes
-- =============================================================================

-- Tenants indexes
CREATE INDEX idx_tenants_status ON tenants(status);
CREATE INDEX idx_tenants_tier ON tenants(tier);
CREATE INDEX idx_tenants_created_at ON tenants(created_at);
CREATE INDEX idx_tenants_contact_email ON tenants(contact_email);

-- Tenant configurations indexes
CREATE INDEX idx_tenant_configs_tenant ON tenant_configurations(tenant_id);

-- Tenant metadata indexes  
CREATE INDEX idx_tenant_metadata_tenant ON tenant_metadata(tenant_id);
CREATE INDEX idx_tenant_metadata_scope ON tenant_metadata(tenant_id, scope);

-- Idempotency keys indexes
CREATE INDEX idx_idempotency_expires ON idempotency_keys(expires_at);
CREATE INDEX idx_idempotency_tenant ON idempotency_keys(tenant_id) WHERE tenant_id IS NOT NULL;

-- Provisioning events indexes
CREATE INDEX idx_prov_events_tenant ON tenant_provisioning_events(tenant_id);
CREATE INDEX idx_prov_events_emitted ON tenant_provisioning_events(emitted_at);
CREATE INDEX idx_prov_events_type ON tenant_provisioning_events(event_type);
CREATE INDEX idx_prov_events_status ON tenant_provisioning_events(status) WHERE status != 'delivered';

-- =============================================================================
-- Triggers for updated_at
-- =============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_tenants_updated_at
    BEFORE UPDATE ON tenants
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_tenant_configs_updated_at
    BEFORE UPDATE ON tenant_configurations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_tenant_metadata_updated_at
    BEFORE UPDATE ON tenant_metadata
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Row Level Security (RLS) Policies for Tenant Isolation
-- =============================================================================

ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_configurations ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_metadata ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_provisioning_events ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own tenant
CREATE POLICY tenant_isolation_policy ON tenants
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

CREATE POLICY tenant_config_isolation_policy ON tenant_configurations
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

CREATE POLICY tenant_metadata_isolation_policy ON tenant_metadata
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

CREATE POLICY tenant_events_isolation_policy ON tenant_provisioning_events
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

-- Platform admin bypass policy (requires role)
CREATE POLICY platform_admin_policy ON tenants
    FOR ALL
    TO platform_admin
    USING (true);

CREATE POLICY platform_admin_config_policy ON tenant_configurations
    FOR ALL
    TO platform_admin
    USING (true);

CREATE POLICY platform_admin_metadata_policy ON tenant_metadata
    FOR ALL
    TO platform_admin
    USING (true);

CREATE POLICY platform_admin_events_policy ON tenant_provisioning_events
    FOR ALL
    TO platform_admin
    USING (true);
