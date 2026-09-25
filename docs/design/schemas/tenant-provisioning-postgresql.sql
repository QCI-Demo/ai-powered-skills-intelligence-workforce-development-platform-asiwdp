-- ============================================================================
-- ASIWDP Tenant Provisioning Schema - PostgreSQL DDL
-- Version: 1.0.0
-- Description: Relational schema for tenant provisioning with tenant_id
--              as partition key for all tenant-scoped tables.
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- ENUMERATED TYPES
-- ============================================================================

CREATE TYPE tenant_status AS ENUM (
    'pending',
    'active',
    'suspended',
    'deprovisioned',
    'failed'
);

CREATE TYPE plan_tier AS ENUM (
    'free',
    'starter',
    'professional',
    'enterprise',
    'custom'
);

CREATE TYPE config_category AS ENUM (
    'general',
    'security',
    'integration',
    'feature_flags',
    'branding',
    'notifications',
    'compliance'
);

CREATE TYPE event_status AS ENUM (
    'pending',
    'published',
    'failed',
    'acknowledged'
);

-- ============================================================================
-- CORE TENANT TABLE
-- ============================================================================

CREATE TABLE tenants (
    tenant_id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                VARCHAR(255) NOT NULL,
    display_name        VARCHAR(500),
    domain              VARCHAR(255) UNIQUE,
    status              tenant_status NOT NULL DEFAULT 'pending',
    plan_tier           plan_tier NOT NULL DEFAULT 'starter',
    settings            JSONB NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by          VARCHAR(255) NOT NULL,
    provisioned_at      TIMESTAMPTZ,
    deprovisioned_at    TIMESTAMPTZ,
    
    CONSTRAINT tenants_name_not_empty CHECK (LENGTH(TRIM(name)) > 0)
);

-- Indexes for tenant lookup
CREATE INDEX idx_tenants_status ON tenants(status);
CREATE INDEX idx_tenants_plan_tier ON tenants(plan_tier);
CREATE INDEX idx_tenants_created_at ON tenants(created_at);
CREATE INDEX idx_tenants_name_lower ON tenants(LOWER(name));

-- ============================================================================
-- TENANT CONFIGURATION TABLE
-- ============================================================================

CREATE TABLE tenant_configurations (
    config_id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id           UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    config_key          VARCHAR(255) NOT NULL,
    config_value        JSONB NOT NULL,
    category            config_category NOT NULL DEFAULT 'general',
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    version             INTEGER NOT NULL DEFAULT 1,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT uq_tenant_config_key UNIQUE (tenant_id, config_key)
);

-- Indexes for configuration lookup
CREATE INDEX idx_tenant_configs_tenant_id ON tenant_configurations(tenant_id);
CREATE INDEX idx_tenant_configs_category ON tenant_configurations(tenant_id, category);
CREATE INDEX idx_tenant_configs_active ON tenant_configurations(tenant_id, is_active);

-- ============================================================================
-- TENANT METADATA TABLE
-- ============================================================================

CREATE TABLE tenant_metadata (
    metadata_id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id           UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    metadata_key        VARCHAR(255) NOT NULL,
    metadata_value      TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT uq_tenant_metadata_key UNIQUE (tenant_id, metadata_key)
);

-- Index for metadata lookup
CREATE INDEX idx_tenant_metadata_tenant_id ON tenant_metadata(tenant_id);

-- ============================================================================
-- IDEMPOTENCY KEY STORE
-- ============================================================================

CREATE TABLE idempotency_keys (
    idempotency_key     VARCHAR(255) PRIMARY KEY,
    tenant_id           UUID,
    request_hash        VARCHAR(64) NOT NULL,
    response_body       JSONB NOT NULL,
    status_code         INTEGER NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at          TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '24 hours')
);

-- Index for cleanup job
CREATE INDEX idx_idempotency_expires ON idempotency_keys(expires_at);

-- ============================================================================
-- PROVISIONING EVENTS TABLE
-- ============================================================================

CREATE TABLE provisioning_events (
    event_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id           UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    event_type          VARCHAR(100) NOT NULL,
    event_payload       JSONB NOT NULL,
    status              event_status NOT NULL DEFAULT 'pending',
    published_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for event processing
CREATE INDEX idx_prov_events_tenant_type ON provisioning_events(tenant_id, event_type);
CREATE INDEX idx_prov_events_status ON provisioning_events(status) WHERE status = 'pending';
CREATE INDEX idx_prov_events_created_at ON provisioning_events(created_at);

-- ============================================================================
-- TENANT AUDIT LOG TABLE
-- ============================================================================

CREATE TABLE tenant_audit_logs (
    audit_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id           UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    action              VARCHAR(100) NOT NULL,
    actor_id            VARCHAR(255) NOT NULL,
    actor_type          VARCHAR(50) NOT NULL DEFAULT 'user',
    resource_type       VARCHAR(100) NOT NULL,
    resource_id         VARCHAR(255),
    changes             JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for audit queries
CREATE INDEX idx_audit_tenant_created ON tenant_audit_logs(tenant_id, created_at DESC);
CREATE INDEX idx_audit_actor ON tenant_audit_logs(actor_id);
CREATE INDEX idx_audit_resource ON tenant_audit_logs(resource_type, resource_id);

-- ============================================================================
-- UPDATE TRIGGER FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers
CREATE TRIGGER update_tenants_updated_at
    BEFORE UPDATE ON tenants
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tenant_configurations_updated_at
    BEFORE UPDATE ON tenant_configurations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tenant_metadata_updated_at
    BEFORE UPDATE ON tenant_metadata
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- DEFAULT CONFIGURATION SEED FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION seed_default_tenant_config(p_tenant_id UUID)
RETURNS VOID AS $$
BEGIN
    -- General settings
    INSERT INTO tenant_configurations (tenant_id, config_key, config_value, category)
    VALUES
        (p_tenant_id, 'max_users', '100', 'general'),
        (p_tenant_id, 'max_organizations', '10', 'general'),
        (p_tenant_id, 'timezone', '"UTC"', 'general'),
        (p_tenant_id, 'locale', '"en-US"', 'general');

    -- Security settings
    INSERT INTO tenant_configurations (tenant_id, config_key, config_value, category)
    VALUES
        (p_tenant_id, 'session_timeout_minutes', '60', 'security'),
        (p_tenant_id, 'mfa_required', 'false', 'security'),
        (p_tenant_id, 'password_policy', '{"min_length": 8, "require_uppercase": true, "require_number": true}', 'security'),
        (p_tenant_id, 'allowed_ip_ranges', '[]', 'security');

    -- Feature flags
    INSERT INTO tenant_configurations (tenant_id, config_key, config_value, category)
    VALUES
        (p_tenant_id, 'skills_ai_enabled', 'true', 'feature_flags'),
        (p_tenant_id, 'learning_paths_enabled', 'true', 'feature_flags'),
        (p_tenant_id, 'analytics_dashboard_enabled', 'true', 'feature_flags'),
        (p_tenant_id, 'api_access_enabled', 'false', 'feature_flags');

    -- Compliance settings
    INSERT INTO tenant_configurations (tenant_id, config_key, config_value, category)
    VALUES
        (p_tenant_id, 'data_retention_days', '365', 'compliance'),
        (p_tenant_id, 'gdpr_enabled', 'true', 'compliance'),
        (p_tenant_id, 'audit_logging_enabled', 'true', 'compliance');

    -- Notification settings
    INSERT INTO tenant_configurations (tenant_id, config_key, config_value, category)
    VALUES
        (p_tenant_id, 'email_notifications_enabled', 'true', 'notifications'),
        (p_tenant_id, 'webhook_url', 'null', 'notifications');
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- CLEANUP FUNCTION FOR EXPIRED IDEMPOTENCY KEYS
-- ============================================================================

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

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE tenants IS 'Core tenant entities with tenant_id as partition key';
COMMENT ON TABLE tenant_configurations IS 'Key-value configuration store per tenant';
COMMENT ON TABLE tenant_metadata IS 'Arbitrary metadata storage per tenant';
COMMENT ON TABLE idempotency_keys IS 'Idempotency key store for safe request replay';
COMMENT ON TABLE provisioning_events IS 'Event log for downstream event processing';
COMMENT ON TABLE tenant_audit_logs IS 'Audit trail for compliance and debugging';
