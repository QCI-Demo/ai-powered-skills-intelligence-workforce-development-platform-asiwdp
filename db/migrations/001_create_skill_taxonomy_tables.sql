-- =============================================================================
-- ASIWDP Skills Framework — PostgreSQL skill taxonomy schema
-- Story: Implement Persistent Domain Model in PostgreSQL & MongoDB
--
-- Entity → table mapping:
--   Skill                  → skill
--   Proficiency            → proficiency
--   Role                   → role
--   CompetencyRequirement  → competency_requirement
--   AuditLog               → audit_log
--
-- Design notes:
--   • tenant_id isolates every row for multi-tenant reads/writes
--   • version supports optimistic concurrency and taxonomy snapshots
--   • Composite indexes on (tenant_id, version) target <50 ms tenant-scoped reads
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- -----------------------------------------------------------------------------
-- skill — authoritative skill taxonomy node (optionally hierarchical)
-- -----------------------------------------------------------------------------
CREATE TABLE skill (
    id              UUID            NOT NULL DEFAULT gen_random_uuid(),
    tenant_id       UUID            NOT NULL,
    version         BIGINT          NOT NULL DEFAULT 1,
    code            VARCHAR(64)     NOT NULL,
    name            VARCHAR(256)    NOT NULL,
    description     TEXT,
    category        VARCHAR(128),
    parent_skill_id UUID,
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    effective_from  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    effective_to    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT pk_skill PRIMARY KEY (id),
    CONSTRAINT fk_skill_parent
        FOREIGN KEY (parent_skill_id) REFERENCES skill (id)
        ON DELETE SET NULL,
    CONSTRAINT uq_skill_tenant_code_version
        UNIQUE (tenant_id, code, version),
    CONSTRAINT ck_skill_version_positive
        CHECK (version > 0),
    CONSTRAINT ck_skill_effective_range
        CHECK (effective_to IS NULL OR effective_to > effective_from)
);

-- -----------------------------------------------------------------------------
-- proficiency — ordered proficiency levels within a tenant taxonomy version
-- -----------------------------------------------------------------------------
CREATE TABLE proficiency (
    id              UUID            NOT NULL DEFAULT gen_random_uuid(),
    tenant_id       UUID            NOT NULL,
    version         BIGINT          NOT NULL DEFAULT 1,
    code            VARCHAR(64)     NOT NULL,
    name            VARCHAR(128)    NOT NULL,
    description     TEXT,
    rank_order      SMALLINT        NOT NULL,
    scale_min       SMALLINT        NOT NULL DEFAULT 1,
    scale_max       SMALLINT        NOT NULL DEFAULT 5,
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT pk_proficiency PRIMARY KEY (id),
    CONSTRAINT uq_proficiency_tenant_code_version
        UNIQUE (tenant_id, code, version),
    CONSTRAINT uq_proficiency_tenant_rank_version
        UNIQUE (tenant_id, rank_order, version),
    CONSTRAINT ck_proficiency_version_positive
        CHECK (version > 0),
    CONSTRAINT ck_proficiency_rank_positive
        CHECK (rank_order > 0),
    CONSTRAINT ck_proficiency_scale
        CHECK (scale_min >= 0 AND scale_max > scale_min)
);

-- -----------------------------------------------------------------------------
-- role — workforce / job role definitions
-- -----------------------------------------------------------------------------
CREATE TABLE role (
    id              UUID            NOT NULL DEFAULT gen_random_uuid(),
    tenant_id       UUID            NOT NULL,
    version         BIGINT          NOT NULL DEFAULT 1,
    code            VARCHAR(64)     NOT NULL,
    name            VARCHAR(256)    NOT NULL,
    description     TEXT,
    job_family      VARCHAR(128),
    level_band      VARCHAR(64),
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    effective_from  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    effective_to    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT pk_role PRIMARY KEY (id),
    CONSTRAINT uq_role_tenant_code_version
        UNIQUE (tenant_id, code, version),
    CONSTRAINT ck_role_version_positive
        CHECK (version > 0),
    CONSTRAINT ck_role_effective_range
        CHECK (effective_to IS NULL OR effective_to > effective_from)
);

-- -----------------------------------------------------------------------------
-- competency_requirement — role → skill mapping with required proficiency
-- -----------------------------------------------------------------------------
CREATE TABLE competency_requirement (
    id                  UUID            NOT NULL DEFAULT gen_random_uuid(),
    tenant_id           UUID            NOT NULL,
    version             BIGINT          NOT NULL DEFAULT 1,
    role_id             UUID            NOT NULL,
    skill_id            UUID            NOT NULL,
    proficiency_id      UUID            NOT NULL,
    requirement_type    VARCHAR(32)     NOT NULL DEFAULT 'REQUIRED',
    weight              NUMERIC(5, 2)   NOT NULL DEFAULT 1.00,
    is_mandatory        BOOLEAN         NOT NULL DEFAULT TRUE,
    notes               TEXT,
    effective_from      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    effective_to        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT pk_competency_requirement PRIMARY KEY (id),
    CONSTRAINT fk_comp_req_role
        FOREIGN KEY (role_id) REFERENCES role (id)
        ON DELETE CASCADE,
    CONSTRAINT fk_comp_req_skill
        FOREIGN KEY (skill_id) REFERENCES skill (id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_comp_req_proficiency
        FOREIGN KEY (proficiency_id) REFERENCES proficiency (id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_comp_req_tenant_role_skill_version
        UNIQUE (tenant_id, role_id, skill_id, version),
    CONSTRAINT ck_comp_req_version_positive
        CHECK (version > 0),
    CONSTRAINT ck_comp_req_weight
        CHECK (weight > 0),
    CONSTRAINT ck_comp_req_type
        CHECK (requirement_type IN ('REQUIRED', 'PREFERRED', 'OPTIONAL')),
    CONSTRAINT ck_comp_req_effective_range
        CHECK (effective_to IS NULL OR effective_to > effective_from)
);

-- -----------------------------------------------------------------------------
-- audit_log — append-only change history (blobs / extensible attrs in MongoDB)
-- -----------------------------------------------------------------------------
CREATE TABLE audit_log (
    id                  UUID            NOT NULL DEFAULT gen_random_uuid(),
    tenant_id           UUID            NOT NULL,
    version             BIGINT          NOT NULL DEFAULT 1,
    entity_type         VARCHAR(64)     NOT NULL,
    entity_id           UUID            NOT NULL,
    action              VARCHAR(32)     NOT NULL,
    actor_id            UUID,
    correlation_id      UUID,
    change_summary      TEXT,
    mongo_blob_ref      VARCHAR(128),
    occurred_at         TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT pk_audit_log PRIMARY KEY (id),
    CONSTRAINT ck_audit_log_version_positive
        CHECK (version > 0),
    CONSTRAINT ck_audit_log_entity_type
        CHECK (entity_type IN (
            'skill',
            'proficiency',
            'role',
            'competency_requirement'
        )),
    CONSTRAINT ck_audit_log_action
        CHECK (action IN ('CREATE', 'UPDATE', 'DELETE', 'IMPORT', 'EXPORT', 'PUBLISH'))
);

-- =============================================================================
-- Indexes — tenant_id, version, and hot read paths (<50 ms)
-- =============================================================================

-- skill
CREATE INDEX idx_skill_tenant_id
    ON skill (tenant_id);
CREATE INDEX idx_skill_version
    ON skill (version);
CREATE INDEX idx_skill_tenant_version
    ON skill (tenant_id, version);
CREATE INDEX idx_skill_tenant_active_code
    ON skill (tenant_id, code)
    WHERE is_active = TRUE;
CREATE INDEX idx_skill_tenant_parent
    ON skill (tenant_id, parent_skill_id)
    WHERE parent_skill_id IS NOT NULL;

-- proficiency
CREATE INDEX idx_proficiency_tenant_id
    ON proficiency (tenant_id);
CREATE INDEX idx_proficiency_version
    ON proficiency (version);
CREATE INDEX idx_proficiency_tenant_version
    ON proficiency (tenant_id, version);
CREATE INDEX idx_proficiency_tenant_rank
    ON proficiency (tenant_id, version, rank_order);

-- role
CREATE INDEX idx_role_tenant_id
    ON role (tenant_id);
CREATE INDEX idx_role_version
    ON role (version);
CREATE INDEX idx_role_tenant_version
    ON role (tenant_id, version);
CREATE INDEX idx_role_tenant_active_code
    ON role (tenant_id, code)
    WHERE is_active = TRUE;

-- competency_requirement
CREATE INDEX idx_comp_req_tenant_id
    ON competency_requirement (tenant_id);
CREATE INDEX idx_comp_req_version
    ON competency_requirement (version);
CREATE INDEX idx_comp_req_tenant_version
    ON competency_requirement (tenant_id, version);
CREATE INDEX idx_comp_req_tenant_role
    ON competency_requirement (tenant_id, role_id, version);
CREATE INDEX idx_comp_req_tenant_skill
    ON competency_requirement (tenant_id, skill_id, version);
CREATE INDEX idx_comp_req_proficiency_id
    ON competency_requirement (proficiency_id);

-- audit_log (append-heavy; indexed for tenant-scoped timeline reads)
CREATE INDEX idx_audit_log_tenant_id
    ON audit_log (tenant_id);
CREATE INDEX idx_audit_log_version
    ON audit_log (version);
CREATE INDEX idx_audit_log_tenant_version
    ON audit_log (tenant_id, version);
CREATE INDEX idx_audit_log_tenant_entity
    ON audit_log (tenant_id, entity_type, entity_id, occurred_at DESC);
CREATE INDEX idx_audit_log_tenant_occurred
    ON audit_log (tenant_id, occurred_at DESC);
