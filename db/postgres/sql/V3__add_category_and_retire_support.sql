-- ASIWDP Skills Framework: category entity + retire support
-- Story: 69c7aeba-9db5-4b83-89ec-9d49d17c41ff
--
-- Adds first-class category taxonomy rows, proficiency.status for retire,
-- and expands audit_log action/entity checks.

-- ---------------------------------------------------------------------------
-- category
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS category (
    id                  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID         NOT NULL,
    version             INTEGER      NOT NULL DEFAULT 1,
    code                VARCHAR(64)  NOT NULL,
    name                VARCHAR(255) NOT NULL,
    description         TEXT,
    parent_category_id  UUID,
    status              VARCHAR(32)  NOT NULL DEFAULT 'active',
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_category_version_positive CHECK (version >= 1),
    CONSTRAINT chk_category_status CHECK (status IN ('active', 'deprecated', 'draft')),
    CONSTRAINT uq_category_tenant_code_version UNIQUE (tenant_id, code, version),
    CONSTRAINT fk_category_parent
        FOREIGN KEY (parent_category_id) REFERENCES category (id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_category_tenant_id
    ON category (tenant_id);
CREATE INDEX IF NOT EXISTS idx_category_version
    ON category (version);
CREATE INDEX IF NOT EXISTS idx_category_tenant_version
    ON category (tenant_id, version);
CREATE INDEX IF NOT EXISTS idx_category_tenant_status
    ON category (tenant_id, status);

-- ---------------------------------------------------------------------------
-- proficiency.status (retire support)
-- ---------------------------------------------------------------------------
ALTER TABLE proficiency
    ADD COLUMN IF NOT EXISTS status VARCHAR(32) NOT NULL DEFAULT 'active';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_proficiency_status'
    ) THEN
        ALTER TABLE proficiency
            ADD CONSTRAINT chk_proficiency_status
            CHECK (status IN ('active', 'deprecated', 'draft'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_proficiency_tenant_status
    ON proficiency (tenant_id, status);

-- ---------------------------------------------------------------------------
-- audit_log: allow category entity + RETIRE action
-- ---------------------------------------------------------------------------
ALTER TABLE audit_log DROP CONSTRAINT IF EXISTS chk_audit_action;
ALTER TABLE audit_log
    ADD CONSTRAINT chk_audit_action CHECK (
        action IN ('CREATE', 'UPDATE', 'DELETE', 'PUBLISH', 'IMPORT', 'ROLLBACK', 'RETIRE')
    );

ALTER TABLE audit_log DROP CONSTRAINT IF EXISTS chk_audit_entity_type;
ALTER TABLE audit_log
    ADD CONSTRAINT chk_audit_entity_type CHECK (
        entity_type IN (
            'skill', 'proficiency', 'role', 'competency_requirement',
            'taxonomy', 'category'
        )
    );

-- ---------------------------------------------------------------------------
-- Seed categories for demo tenant (aligned with skill.category strings)
-- ---------------------------------------------------------------------------
INSERT INTO category (id, tenant_id, version, code, name, description, status)
VALUES
    ('e5000001-0000-4000-8000-000000000001',
     '22222222-2222-2222-2222-222222222222', 1, 'FOUNDATIONAL',
     'Foundational', 'Core literacy and baseline competencies.', 'active'),
    ('e5000001-0000-4000-8000-000000000002',
     '22222222-2222-2222-2222-222222222222', 1, 'TECHNICAL',
     'Technical', 'Technical and engineering skills.', 'active'),
    ('e5000001-0000-4000-8000-000000000003',
     '22222222-2222-2222-2222-222222222222', 1, 'BEHAVIORAL',
     'Behavioral', 'Interpersonal and communication competencies.', 'active')
ON CONFLICT (tenant_id, code, version) DO NOTHING;
