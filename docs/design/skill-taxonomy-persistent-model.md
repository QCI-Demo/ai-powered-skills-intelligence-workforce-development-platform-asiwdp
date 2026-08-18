# Skills Taxonomy Persistent Domain Model

**Story:** Implement Persistent Domain Model in PostgreSQL & MongoDB  
**Story ID:** `5ea02ecb-2f38-4d9b-a964-8cef5f85acac`  
**Epic:** Skills Framework & Competency Management Services  
**Project:** ASIWDP

## 1. Purpose

Define the authoritative, tenant-scoped persistence model for the skills
taxonomy: relational core entities in PostgreSQL and flexible attribute
documents in MongoDB. The design targets sub-50 ms tenant-scoped reads via
covering indexes on `(tenant_id, version)` and common lookup keys.

## 2. Storage split

| Store | Responsibility |
|-------|----------------|
| PostgreSQL | Normalized skill taxonomy: `skill`, `proficiency`, `role`, `competency_requirement`, `audit_log` |
| MongoDB | Extensible metadata / audit blobs: `skill_meta`, `role_meta` |

Every record is isolated by `tenant_id`. Taxonomy evolution is tracked by an
integer `version` column/field (optimistic concurrency + published taxonomy
revision).

## 3. PostgreSQL entity map

```
tenant_id ──┬── skill ───────────────┐
            │                        │
            ├── proficiency ─────────┼── competency_requirement
            │                        │
            ├── role ────────────────┘
            │
            └── audit_log
```

| Entity | Table | Notes |
|--------|-------|-------|
| Skill | `skill` | Hierarchical via optional `parent_skill_id` |
| Proficiency | `proficiency` | Ordered scale levels (`rank_order`) |
| Role | `role` | Job / workforce role (not IAM role) |
| Competency requirement | `competency_requirement` | Role → skill + required proficiency |
| Audit log | `audit_log` | Append-only change history |

### 3.1 Shared columns

| Column | Type | Purpose |
|--------|------|---------|
| `id` | `UUID` | Primary key |
| `tenant_id` | `UUID` | Tenant isolation key |
| `version` | `INTEGER` | Taxonomy / row revision (≥ 1) |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | Audit timestamps |

### 3.2 Indexes for &lt;50 ms reads

Primary access patterns are always tenant-scoped:

- `(tenant_id, version)` on every table
- `(tenant_id, code, version)` unique where codes exist
- FK join helpers: `(tenant_id, role_id)`, `(tenant_id, skill_id)`
- Audit time-range: `(tenant_id, created_at DESC)`

## 4. MongoDB collections

| Collection | Key fields | Payload |
|------------|------------|---------|
| `skill_meta` | `tenant_id`, `skill_id`, `version` | `metadata` object, `audit_entries[]` |
| `role_meta` | `tenant_id`, `role_id`, `version` | `metadata` object, `audit_entries[]` |

JSON Schema validators reject documents missing `tenant_id` / `version`.
Unique compound indexes enforce one meta document per
`(tenant_id, skill_id|role_id, version)`.

## 5. Migrations & seed

Flyway migrations live under `db/postgres/sql/`:

1. `V1__create_skill_taxonomy_schema.sql` — DDL + indexes  
2. `V2__seed_demo_tenant_taxonomy.sql` — idempotent demo-tenant seed  

Undo counterparts in `db/postgres/undo/` (`U1__…`, `U2__…`) support down
migrations (applied manually or via Liquibase rollback). Seed inserts use
`ON CONFLICT DO NOTHING` so re-runs are safe.

## 6. Data-access layer

Python package `asiwdp-skills-persistence` (`libs/skills-persistence`) provides
MongoDB CRUD repositories for `skill_meta` and `role_meta`, plus helpers to
ensure validated collections/indexes exist.
