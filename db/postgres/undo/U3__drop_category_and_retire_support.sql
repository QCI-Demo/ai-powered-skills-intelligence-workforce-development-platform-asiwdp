-- Undo V3__add_category_and_retire_support.sql

DROP INDEX IF EXISTS idx_proficiency_tenant_status;
ALTER TABLE proficiency DROP CONSTRAINT IF EXISTS chk_proficiency_status;
ALTER TABLE proficiency DROP COLUMN IF EXISTS status;

DROP INDEX IF EXISTS idx_category_tenant_status;
DROP INDEX IF EXISTS idx_category_tenant_version;
DROP INDEX IF EXISTS idx_category_version;
DROP INDEX IF EXISTS idx_category_tenant_id;
DROP TABLE IF EXISTS category;

ALTER TABLE audit_log DROP CONSTRAINT IF EXISTS chk_audit_action;
ALTER TABLE audit_log
    ADD CONSTRAINT chk_audit_action CHECK (
        action IN ('CREATE', 'UPDATE', 'DELETE', 'PUBLISH', 'IMPORT', 'ROLLBACK')
    );

ALTER TABLE audit_log DROP CONSTRAINT IF EXISTS chk_audit_entity_type;
ALTER TABLE audit_log
    ADD CONSTRAINT chk_audit_entity_type CHECK (
        entity_type IN (
            'skill', 'proficiency', 'role', 'competency_requirement', 'taxonomy'
        )
    );
