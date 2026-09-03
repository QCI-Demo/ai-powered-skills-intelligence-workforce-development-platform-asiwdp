# Skill Taxonomy Persistent Model — Migration Notes

## Scope

Flyway / Liquibase scripts create the PostgreSQL relational schema for:

| Entity | Table |
|--------|-------|
| Skill | `skill` |
| Proficiency | `proficiency` |
| Role | `role` |
| CompetencyRequirement | `competency_requirement` |
| AuditLog | `audit_log` |

Flexible metadata and audit blobs remain in MongoDB (`skill_meta`, `role_meta`).

## Tenant isolation

Shared-schema, row-level isolation via mandatory `tenant_id UUID` on every table.
Uniqueness is scoped as `(tenant_id, code, version)` (and equivalent composites).

## Versioning

`version INTEGER >= 1` supports taxonomy snapshots and optimistic concurrency.
Initial seed loads version `1` for the demo tenant.

## Idempotency

- DDL uses `CREATE TABLE / INDEX IF NOT EXISTS`
- Seed uses fixed UUIDs + `ON CONFLICT DO NOTHING`
- `asiwdp_seed_tenant_taxonomy(tenant_id, version)` is safe to re-run
- Down scripts delete only the demo-tenant rows / drop tables in dependency order
