-- ASIWDP Tenant Provisioning schema (PostgreSQL)
-- Story: 486d3e38-2cec-40cb-874d-576d2147732c
-- Task:  89d8dbba-19a6-4a35-8382-d1be49c1fcf0
--
-- Tables: tenant, tenant_configuration, tenant_metadata, idempotency_record
-- Partition / isolation key: tenant_id on every tenant-owned row.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- tenant (canonical tenant record; tenant_id is both PK and partition key)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tenant (
    tenant_id        UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    slug             VARCHAR(64)  NOT NULL,
    display_name     VARCHAR(255) NOT NULL,
    status           VARCHAR(32)  NOT NULL DEFAULT 'provisioning',
    plan_code        VARCHAR(64)  NOT NULL DEFAULT 'standard',
    data_residency   VARCHAR(64)  NOT NULL DEFAULT 'us-east',
    created_by       UUID,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    provisioned_at   TIMESTAMPTZ,
    CONSTRAINT chk_tenant_status
        CHECK (status IN ('provisioning', 'active', 'suspended', 'decommissioned')),
    CONSTRAINT uq_tenant_slug UNIQUE (slug)
);

-- Explicit partition-key index (PK already covers equality; keeps scan patterns consistent)
CREATE INDEX IF NOT EXISTS idx_tenant_tenant_id ON tenant (tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_status ON tenant (status);
CREATE INDEX IF NOT EXISTS idx_tenant_created_at ON tenant (created_at DESC);

COMMENT ON TABLE tenant IS 'Platform tenant registry; tenant_id is the isolation partition key.';
COMMENT ON COLUMN tenant.tenant_id IS 'Partition key for all tenant-scoped data.';

-- ---------------------------------------------------------------------------
-- tenant_configuration (1:1 defaults applied at provision time)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tenant_configuration (
    tenant_id          UUID         PRIMARY KEY
        REFERENCES tenant (tenant_id) ON DELETE CASCADE,
    defaults           JSONB        NOT NULL DEFAULT '{}'::jsonb,
    locale             VARCHAR(32)  NOT NULL DEFAULT 'en-US',
    timezone           VARCHAR(64)  NOT NULL DEFAULT 'UTC',
    metering_enabled   BOOLEAN      NOT NULL DEFAULT TRUE,
    gdpr_enabled       BOOLEAN      NOT NULL DEFAULT TRUE,
    ccpa_enabled       BOOLEAN      NOT NULL DEFAULT TRUE,
    schema_version     INTEGER      NOT NULL DEFAULT 1,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_tenant_configuration_schema_version
        CHECK (schema_version >= 1)
);

CREATE INDEX IF NOT EXISTS idx_tenant_configuration_tenant_id
    ON tenant_configuration (tenant_id);

COMMENT ON TABLE tenant_configuration IS
    'Default configuration seeded atomically with tenant creation.';

-- ---------------------------------------------------------------------------
-- tenant_metadata (extensible tenant-scoped key/value metadata)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tenant_metadata (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    UUID         NOT NULL
        REFERENCES tenant (tenant_id) ON DELETE CASCADE,
    meta_key     VARCHAR(128) NOT NULL,
    meta_value   JSONB        NOT NULL DEFAULT '{}'::jsonb,
    created_by   VARCHAR(128),
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_tenant_metadata_tenant_key UNIQUE (tenant_id, meta_key)
);

CREATE INDEX IF NOT EXISTS idx_tenant_metadata_tenant_id
    ON tenant_metadata (tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_metadata_tenant_key
    ON tenant_metadata (tenant_id, meta_key);

COMMENT ON COLUMN tenant_metadata.tenant_id IS 'Partition key.';

-- ---------------------------------------------------------------------------
-- idempotency_record (Idempotency-Key → provisioned tenant response)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS idempotency_record (
    idempotency_key  VARCHAR(128) NOT NULL,
    tenant_id        UUID         NOT NULL
        REFERENCES tenant (tenant_id) ON DELETE CASCADE,
    request_hash     VARCHAR(64)  NOT NULL,
    response_status  INTEGER      NOT NULL,
    response_body    JSONB        NOT NULL,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    expires_at       TIMESTAMPTZ  NOT NULL,
    PRIMARY KEY (idempotency_key),
    CONSTRAINT chk_idempotency_status CHECK (response_status BETWEEN 200 AND 599)
);

CREATE INDEX IF NOT EXISTS idx_idempotency_tenant_id
    ON idempotency_record (tenant_id);
CREATE INDEX IF NOT EXISTS idx_idempotency_expires_at
    ON idempotency_record (expires_at);

COMMENT ON TABLE idempotency_record IS
    'Stores Idempotency-Key outcomes for POST /api/tenants replay safety.';
