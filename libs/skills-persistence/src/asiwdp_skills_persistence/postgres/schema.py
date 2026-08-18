"""Expected PostgreSQL schema metadata for migration verification."""

from __future__ import annotations

EXPECTED_TABLES: tuple[str, ...] = (
    "skill",
    "proficiency",
    "role",
    "competency_requirement",
    "audit_log",
)

# Index names created in V1__create_skill_taxonomy_schema.sql
EXPECTED_INDEXES: tuple[str, ...] = (
    "idx_skill_tenant_id",
    "idx_skill_version",
    "idx_skill_tenant_version",
    "idx_proficiency_tenant_id",
    "idx_proficiency_version",
    "idx_proficiency_tenant_version",
    "idx_role_tenant_id",
    "idx_role_version",
    "idx_role_tenant_version",
    "idx_competency_tenant_id",
    "idx_competency_version",
    "idx_competency_tenant_version",
    "idx_audit_log_tenant_id",
    "idx_audit_log_version",
    "idx_audit_log_tenant_version",
)

DEMO_TENANT_ID = "22222222-2222-2222-2222-222222222222"
