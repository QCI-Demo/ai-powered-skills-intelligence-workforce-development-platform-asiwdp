-- ASIWDP Tenant Provisioning: core tenant, configuration, metadata schema
-- Story: 486d3e38-2cec-40cb-874d-576d2147732c
-- Task:  89d8dbba-19a6-4a35-8382-d1be49c1fcf0
--
-- tenant_id is the partition / isolation key on all tenant-scoped tables.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- tenant (platform catalog; primary key IS the tenant partition key)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tenant (
    tenant_id        UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    slug             VARCHAR(128) NOT NULL,
    display_name     VARCHAR(255) NOT NULL,
    status           VARCHAR(32)  NOT NULL DEFAULT 'active',
    plan_code        VARCHAR(64)  NOT NULL DEFAULT 'standard',
    region           VARCHAR(64)  NOT NULL DEFAULT 'us-east-1',
    timezone         VARCHAR(64)  NOT NULL DEFAULT 'UTC',
    contact          JSONB        NOT NULL DEFAULT '{}'::jsonb,
    provisioned_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_by       VARCHAR(128) NOT NULL,
    CONSTRAINT chk_tenant_status CHECK (
        status IN ('pending', 'active', 'suspended', 'decommissioned')
    ),
    CONSTRAINT chk_tenant_slug_format CHECK (
        slug ~ '^[a-z0-9]([a-z0-9-]{0,126}[a-z0-9])?$'
    ),
    CONSTRAINT uq_tenant_slug UNIQUE (slug)
);

CREATE INDEX IF NOT EXISTS idx_tenant_status
    ON tenant (status);
CREATE INDEX IF NOT EXISTS idx_tenant_region
    ON tenant (region);
CREATE INDEX IF NOT EXISTS idx_tenant_provisioned_at
    ON tenant (provisioned_at);

-- ---------------------------------------------------------------------------
-- tenant_configuration (partitioned by tenant_id)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tenant_configuration (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID         NOT NULL,
    config_key    VARCHAR(128) NOT NULL,
    config_value  JSONB        NOT NULL DEFAULT '{}'::jsonb,
    is_default    BOOLEAN      NOT NULL DEFAULT FALSE,
    version       INTEGER      NOT NULL DEFAULT 1,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_tenant_configuration_version_positive CHECK (version >= 1),
    CONSTRAINT uq_tenant_configuration_key UNIQUE (tenant_id, config_key),
    CONSTRAINT fk_tenant_configuration_tenant
        FOREIGN KEY (tenant_id) REFERENCES tenant (tenant_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tenant_configuration_tenant_id
    ON tenant_configuration (tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_configuration_tenant_key
    ON tenant_configuration (tenant_id, config_key);

-- ---------------------------------------------------------------------------
-- tenant_metadata (partitioned by tenant_id)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tenant_metadata (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID         NOT NULL,
    meta_key    VARCHAR(128) NOT NULL,
    meta_value  JSONB        NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_tenant_metadata_key UNIQUE (tenant_id, meta_key),
    CONSTRAINT fk_tenant_metadata_tenant
        FOREIGN KEY (tenant_id) REFERENCES tenant (tenant_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tenant_metadata_tenant_id
    ON tenant_metadata (tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_metadata_tenant_key
    ON tenant_metadata (tenant_id, meta_key);

-- ---------------------------------------------------------------------------
-- idempotency_record (client Idempotency-Key → provisioned tenant)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS idempotency_record (
    id                    UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key       VARCHAR(128) NOT NULL,
    requesting_tenant_id  UUID,
    created_tenant_id     UUID         NOT NULL,
    request_hash          VARCHAR(64)  NOT NULL,
    response_status       INTEGER      NOT NULL,
    response_body         JSONB        NOT NULL,
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    expires_at            TIMESTAMPTZ  NOT NULL,
    CONSTRAINT uq_idempotency_key UNIQUE (idempotency_key),
    CONSTRAINT fk_idempotency_created_tenant
        FOREIGN KEY (created_tenant_id) REFERENCES tenant (tenant_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_idempotency_requesting_tenant
    ON idempotency_record (requesting_tenant_id);
CREATE INDEX IF NOT EXISTS idx_idempotency_created_tenant
    ON idempotency_record (created_tenant_id);
CREATE INDEX IF NOT EXISTS idx_idempotency_expires_at
    ON idempotency_record (expires_at);
