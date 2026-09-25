-- =============================================================================
-- ASIWDP Tenant Provisioning Schema - PostgreSQL DDL
-- Task: 89d8dbba-19a6-4a35-8382-d1be49c1fcf0
-- =============================================================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- TENANTS TABLE
-- Core tenant entity with partition key for multi-tenant isolation
-- =============================================================================
CREATE TABLE IF NOT EXISTS tenants (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(255) NOT NULL,
    slug            VARCHAR(128) NOT NULL,
    status          VARCHAR(32) NOT NULL DEFAULT 'provisioning',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      VARCHAR(255) NOT NULL,
    
    CONSTRAINT tenants_slug_unique UNIQUE (slug),
    CONSTRAINT tenants_status_check CHECK (status IN ('provisioning', 'active', 'suspended', 'deleted'))
);

-- Index for status filtering (active tenants query)
CREATE INDEX IF NOT EXISTS idx_tenants_status ON tenants(status);

-- Index for created_at ordering
CREATE INDEX IF NOT EXISTS idx_tenants_created_at ON tenants(created_at DESC);

COMMENT ON TABLE tenants IS 'Core tenant entities for multi-tenant SaaS platform';
COMMENT ON COLUMN tenants.id IS 'Unique tenant identifier - used as partition key across all tenant-scoped data';
COMMENT ON COLUMN tenants.slug IS 'URL-safe unique identifier for tenant (e.g., subdomain)';
COMMENT ON COLUMN tenants.status IS 'Tenant lifecycle status: provisioning -> active -> suspended -> deleted';

-- =============================================================================
-- TENANT_CONFIGURATIONS TABLE
-- Default and customized configuration per tenant
-- =============================================================================
CREATE TABLE IF NOT EXISTS tenant_configurations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL,
    feature_flags   JSONB NOT NULL DEFAULT '{}'::JSONB,
    limits          JSONB NOT NULL DEFAULT '{}'::JSONB,
    branding        JSONB NOT NULL DEFAULT '{}'::JSONB,
    integrations    JSONB NOT NULL DEFAULT '{}'::JSONB,
    config_version  INTEGER NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT tenant_configurations_tenant_fk FOREIGN KEY (tenant_id) 
        REFERENCES tenants(id) ON DELETE CASCADE,
    CONSTRAINT tenant_configurations_tenant_unique UNIQUE (tenant_id)
);

-- GIN indexes for JSONB query performance
CREATE INDEX IF NOT EXISTS idx_tenant_config_feature_flags ON tenant_configurations USING GIN (feature_flags);
CREATE INDEX IF NOT EXISTS idx_tenant_config_limits ON tenant_configurations USING GIN (limits);

COMMENT ON TABLE tenant_configurations IS 'Tenant-specific configuration including feature flags, limits, branding';
COMMENT ON COLUMN tenant_configurations.feature_flags IS 'Feature toggle settings (e.g., {"ai_recommendations": true})';
COMMENT ON COLUMN tenant_configurations.limits IS 'Usage limits (e.g., {"max_users": 100, "max_skills": 1000})';
COMMENT ON COLUMN tenant_configurations.branding IS 'Branding customization (e.g., {"logo_url": "...", "primary_color": "#..."})';
COMMENT ON COLUMN tenant_configurations.integrations IS 'Integration configurations (e.g., {"sso": {...}, "lms": {...}})';
COMMENT ON COLUMN tenant_configurations.config_version IS 'Optimistic concurrency control version';

-- =============================================================================
-- TENANT_METADATA TABLE
-- Extensible key-value metadata for tenants
-- =============================================================================
CREATE TABLE IF NOT EXISTS tenant_metadata (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL,
    key             VARCHAR(255) NOT NULL,
    value           TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT tenant_metadata_tenant_fk FOREIGN KEY (tenant_id) 
        REFERENCES tenants(id) ON DELETE CASCADE,
    CONSTRAINT tenant_metadata_tenant_key_unique UNIQUE (tenant_id, key)
);

-- Composite index for tenant-scoped metadata lookups
CREATE INDEX IF NOT EXISTS idx_tenant_metadata_tenant_key ON tenant_metadata(tenant_id, key);

COMMENT ON TABLE tenant_metadata IS 'Extensible key-value metadata storage for tenant-scoped data';

-- =============================================================================
-- IDEMPOTENCY_KEYS TABLE
-- Ensures idempotent tenant provisioning operations
-- =============================================================================
CREATE TABLE IF NOT EXISTS idempotency_keys (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    idempotency_key VARCHAR(255) NOT NULL,
    tenant_id       UUID,
    request_hash    VARCHAR(64) NOT NULL,
    response        JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '24 hours'),
    
    CONSTRAINT idempotency_keys_key_unique UNIQUE (idempotency_key),
    CONSTRAINT idempotency_keys_tenant_fk FOREIGN KEY (tenant_id) 
        REFERENCES tenants(id) ON DELETE SET NULL
);

-- Index for key lookups
CREATE INDEX IF NOT EXISTS idx_idempotency_keys_key ON idempotency_keys(idempotency_key);

-- Partial index for expired key cleanup
CREATE INDEX IF NOT EXISTS idx_idempotency_keys_expires ON idempotency_keys(expires_at) 
    WHERE expires_at < NOW();

COMMENT ON TABLE idempotency_keys IS 'Idempotency key storage for safe request retries';
COMMENT ON COLUMN idempotency_keys.idempotency_key IS 'Client-provided idempotency key from Idempotency-Key header';
COMMENT ON COLUMN idempotency_keys.request_hash IS 'SHA-256 hash of request body for conflict detection';
COMMENT ON COLUMN idempotency_keys.response IS 'Cached response for replay';
COMMENT ON COLUMN idempotency_keys.expires_at IS 'TTL for automatic cleanup (default 24h)';

-- =============================================================================
-- TRIGGERS FOR updated_at
-- =============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tenants_updated_at
    BEFORE UPDATE ON tenants
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER tenant_configurations_updated_at
    BEFORE UPDATE ON tenant_configurations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER tenant_metadata_updated_at
    BEFORE UPDATE ON tenant_metadata
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- CLEANUP FUNCTION FOR EXPIRED IDEMPOTENCY KEYS
-- =============================================================================
CREATE OR REPLACE FUNCTION cleanup_expired_idempotency_keys()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM idempotency_keys WHERE expires_at < NOW();
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_expired_idempotency_keys IS 'Deletes expired idempotency keys. Call periodically via cron or pg_cron.';
