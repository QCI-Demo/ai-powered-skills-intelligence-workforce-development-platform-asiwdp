-- ASIWDP Skills Framework: core taxonomy schema (PostgreSQL)
-- Story: 5ea02ecb-2f38-4d9b-a964-8cef5f85acac
-- Task:  d7d627a4-7301-438e-9a1c-0670999719f8
--
-- Tables: skill, proficiency, role, competency_requirement, audit_log
-- All tables include tenant_id + version and indexes tuned for <50ms tenant reads.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- skill
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS skill (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        UUID         NOT NULL,
    version          INTEGER      NOT NULL DEFAULT 1,
    code             VARCHAR(64)  NOT NULL,
    name             VARCHAR(255) NOT NULL,
    description      TEXT,
    category         VARCHAR(128),
    parent_skill_id  UUID,
    status           VARCHAR(32)  NOT NULL DEFAULT 'active',
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_skill_version_positive CHECK (version >= 1),
    CONSTRAINT chk_skill_status CHECK (status IN ('active', 'deprecated', 'draft')),
    CONSTRAINT uq_skill_tenant_code_version UNIQUE (tenant_id, code, version),
    CONSTRAINT fk_skill_parent
        FOREIGN KEY (parent_skill_id) REFERENCES skill (id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_skill_tenant_id
    ON skill (tenant_id);
CREATE INDEX IF NOT EXISTS idx_skill_version
    ON skill (version);
CREATE INDEX IF NOT EXISTS idx_skill_tenant_version
    ON skill (tenant_id, version);
CREATE INDEX IF NOT EXISTS idx_skill_tenant_status
    ON skill (tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_skill_tenant_category
    ON skill (tenant_id, category);
CREATE INDEX IF NOT EXISTS idx_skill_parent
    ON skill (parent_skill_id)
    WHERE parent_skill_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- proficiency
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS proficiency (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    UUID         NOT NULL,
    version      INTEGER      NOT NULL DEFAULT 1,
    level        INTEGER      NOT NULL,
    code         VARCHAR(64)  NOT NULL,
    name         VARCHAR(255) NOT NULL,
    description  TEXT,
    rank_order   INTEGER      NOT NULL,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_proficiency_version_positive CHECK (version >= 1),
    CONSTRAINT chk_proficiency_level_positive CHECK (level >= 1),
    CONSTRAINT uq_proficiency_tenant_code_version UNIQUE (tenant_id, code, version),
    CONSTRAINT uq_proficiency_tenant_level_version UNIQUE (tenant_id, level, version)
);

CREATE INDEX IF NOT EXISTS idx_proficiency_tenant_id
    ON proficiency (tenant_id);
CREATE INDEX IF NOT EXISTS idx_proficiency_version
    ON proficiency (version);
CREATE INDEX IF NOT EXISTS idx_proficiency_tenant_version
    ON proficiency (tenant_id, version);
CREATE INDEX IF NOT EXISTS idx_proficiency_tenant_rank
    ON proficiency (tenant_id, rank_order);

-- ---------------------------------------------------------------------------
-- role (workforce / job role within the skills taxonomy — not IAM)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS role (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    UUID         NOT NULL,
    version      INTEGER      NOT NULL DEFAULT 1,
    code         VARCHAR(64)  NOT NULL,
    name         VARCHAR(255) NOT NULL,
    description  TEXT,
    family       VARCHAR(128),
    status       VARCHAR(32)  NOT NULL DEFAULT 'active',
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_role_version_positive CHECK (version >= 1),
    CONSTRAINT chk_role_status CHECK (status IN ('active', 'deprecated', 'draft')),
    CONSTRAINT uq_role_tenant_code_version UNIQUE (tenant_id, code, version)
);

CREATE INDEX IF NOT EXISTS idx_role_tenant_id
    ON role (tenant_id);
CREATE INDEX IF NOT EXISTS idx_role_version
    ON role (version);
CREATE INDEX IF NOT EXISTS idx_role_tenant_version
    ON role (tenant_id, version);
CREATE INDEX IF NOT EXISTS idx_role_tenant_family
    ON role (tenant_id, family);

-- ---------------------------------------------------------------------------
-- competency_requirement (role → skill + required proficiency)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS competency_requirement (
    id               UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        UUID          NOT NULL,
    version          INTEGER       NOT NULL DEFAULT 1,
    role_id          UUID          NOT NULL,
    skill_id         UUID          NOT NULL,
    proficiency_id   UUID          NOT NULL,
    is_required      BOOLEAN       NOT NULL DEFAULT TRUE,
    weight           NUMERIC(5, 2) NOT NULL DEFAULT 1.00,
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_competency_version_positive CHECK (version >= 1),
    CONSTRAINT chk_competency_weight_nonneg CHECK (weight >= 0),
    CONSTRAINT uq_competency_role_skill_version
        UNIQUE (tenant_id, role_id, skill_id, version),
    CONSTRAINT fk_competency_role
        FOREIGN KEY (role_id) REFERENCES role (id)
        ON DELETE CASCADE,
    CONSTRAINT fk_competency_skill
        FOREIGN KEY (skill_id) REFERENCES skill (id)
        ON DELETE CASCADE,
    CONSTRAINT fk_competency_proficiency
        FOREIGN KEY (proficiency_id) REFERENCES proficiency (id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_competency_tenant_id
    ON competency_requirement (tenant_id);
CREATE INDEX IF NOT EXISTS idx_competency_version
    ON competency_requirement (version);
CREATE INDEX IF NOT EXISTS idx_competency_tenant_version
    ON competency_requirement (tenant_id, version);
CREATE INDEX IF NOT EXISTS idx_competency_tenant_role
    ON competency_requirement (tenant_id, role_id);
CREATE INDEX IF NOT EXISTS idx_competency_tenant_skill
    ON competency_requirement (tenant_id, skill_id);
CREATE INDEX IF NOT EXISTS idx_competency_proficiency
    ON competency_requirement (proficiency_id);

-- ---------------------------------------------------------------------------
-- audit_log (append-only)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID         NOT NULL,
    version       INTEGER      NOT NULL DEFAULT 1,
    entity_type   VARCHAR(64)  NOT NULL,
    entity_id     UUID         NOT NULL,
    action        VARCHAR(32)  NOT NULL,
    actor_id      UUID,
    correlation_id UUID,
    change_blob   JSONB        NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_audit_version_positive CHECK (version >= 1),
    CONSTRAINT chk_audit_action CHECK (
        action IN ('CREATE', 'UPDATE', 'DELETE', 'PUBLISH', 'IMPORT', 'ROLLBACK')
    ),
    CONSTRAINT chk_audit_entity_type CHECK (
        entity_type IN (
            'skill', 'proficiency', 'role', 'competency_requirement', 'taxonomy'
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_audit_log_tenant_id
    ON audit_log (tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_version
    ON audit_log (version);
CREATE INDEX IF NOT EXISTS idx_audit_log_tenant_version
    ON audit_log (tenant_id, version);
CREATE INDEX IF NOT EXISTS idx_audit_log_tenant_created
    ON audit_log (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_entity
    ON audit_log (tenant_id, entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_correlation
    ON audit_log (correlation_id)
    WHERE correlation_id IS NOT NULL;
