-- =============================================================================
-- ASIWDP Tenant Provisioning DDL - PostgreSQL
-- Schema Version: 1.0.0
-- =============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- ENUM Types
-- =============================================================================

CREATE TYPE tenant_status AS ENUM (
    'provisioning',
    'active',
    'suspended',
    'deactivated',
    'failed'
);

CREATE TYPE tenant_tier AS ENUM (
    'free',
    'standard',
    'enterprise'
);

CREATE TYPE idempotency_status AS ENUM (
    'pending',
    'completed',
    'failed'
);

-- =============================================================================
-- Tables
-- =============================================================================

-- Primary tenant table
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL,
    status tenant_status NOT NULL DEFAULT 'provisioning',
    tier tenant_tier NOT NULL DEFAULT 'standard',
    contact_email VARCHAR(320) NOT NULL,
    billing_email VARCHAR(320),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    provisioned_at TIMESTAMPTZ,
    deactivated_at TIMESTAMPTZ,
    created_by UUID NOT NULL,
    
    CONSTRAINT tenants_slug_unique UNIQUE (slug),
    CONSTRAINT tenants_slug_format CHECK (slug ~ '^[a-z0-9][a-z0-9-]*[a-z0-9]$' AND LENGTH(slug) >= 3),
    CONSTRAINT tenants_email_format CHECK (contact_email ~ '^[^@]+@[^@]+\.[^@]+$'),
    CONSTRAINT tenants_billing_email_format CHECK (billing_email IS NULL OR billing_email ~ '^[^@]+@[^@]+\.[^@]+$')
);

-- Tenant configuration key-value store
CREATE TABLE tenant_configurations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    config_key VARCHAR(255) NOT NULL,
    config_value JSONB NOT NULL,
    description TEXT,
    is_sensitive BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1,
    
    CONSTRAINT tenant_configs_key_unique UNIQUE (tenant_id, config_key),
    CONSTRAINT tenant_configs_key_format CHECK (config_key ~ '^[a-z_][a-z0-9_.]*$')
);

-- Idempotency key store for safe retries
CREATE TABLE idempotency_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE SET NULL,
    idempotency_key VARCHAR(255) NOT NULL,
    operation VARCHAR(100) NOT NULL,
    resource_id UUID,
    request_hash VARCHAR(64) NOT NULL,
    response_data JSONB,
    status idempotency_status NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    
    CONSTRAINT idempotency_key_unique UNIQUE (idempotency_key)
);

-- Tenant audit log for compliance and debugging
CREATE TABLE tenant_audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    actor_id UUID NOT NULL,
    actor_type VARCHAR(50) NOT NULL DEFAULT 'user',
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    resource_id UUID,
    old_value JSONB,
    new_value JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- Indexes
-- =============================================================================

-- Tenants indexes
CREATE INDEX idx_tenants_slug ON tenants(slug);
CREATE INDEX idx_tenants_status ON tenants(status);
CREATE INDEX idx_tenants_tier ON tenants(tier);
CREATE INDEX idx_tenants_created_at ON tenants(created_at);
CREATE INDEX idx_tenants_status_created ON tenants(status, created_at);

-- Tenant configurations indexes
CREATE INDEX idx_tenant_configs_tenant_id ON tenant_configurations(tenant_id);
CREATE INDEX idx_tenant_configs_key ON tenant_configurations(config_key);
CREATE INDEX idx_tenant_configs_tenant_key ON tenant_configurations(tenant_id, config_key);

-- Idempotency keys indexes
CREATE INDEX idx_idempotency_expires_at ON idempotency_keys(expires_at);
CREATE INDEX idx_idempotency_status ON idempotency_keys(status);
CREATE INDEX idx_idempotency_operation ON idempotency_keys(operation);

-- Audit logs indexes (partitioning recommended for production)
CREATE INDEX idx_audit_tenant_created ON tenant_audit_logs(tenant_id, created_at);
CREATE INDEX idx_audit_action ON tenant_audit_logs(action);
CREATE INDEX idx_audit_actor ON tenant_audit_logs(actor_id);
CREATE INDEX idx_audit_resource ON tenant_audit_logs(resource_type, resource_id);

-- =============================================================================
-- Triggers for updated_at
-- =============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_tenants_updated_at
    BEFORE UPDATE ON tenants
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tenant_configurations_updated_at
    BEFORE UPDATE ON tenant_configurations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Row Level Security (RLS) for tenant isolation
-- =============================================================================

ALTER TABLE tenant_configurations ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_audit_logs ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see configs for their tenant (set via session variable)
CREATE POLICY tenant_isolation_configs ON tenant_configurations
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);

CREATE POLICY tenant_isolation_audit ON tenant_audit_logs
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);

-- =============================================================================
-- Comments
-- =============================================================================

COMMENT ON TABLE tenants IS 'Primary tenant registry for multi-tenant SaaS platform';
COMMENT ON TABLE tenant_configurations IS 'Tenant-scoped configuration key-value store';
COMMENT ON TABLE idempotency_keys IS 'Idempotency key store for safe request retries';
COMMENT ON TABLE tenant_audit_logs IS 'Immutable audit trail for tenant operations';

COMMENT ON COLUMN tenants.slug IS 'URL-safe unique identifier for tenant';
COMMENT ON COLUMN tenants.tier IS 'Subscription tier determining feature access and limits';
COMMENT ON COLUMN tenants.metadata IS 'Extensible JSON metadata for custom tenant attributes';
COMMENT ON COLUMN tenant_configurations.is_sensitive IS 'Flag for values that should be masked in logs/exports';
COMMENT ON COLUMN idempotency_keys.request_hash IS 'SHA-256 hash of request body for collision detection';
