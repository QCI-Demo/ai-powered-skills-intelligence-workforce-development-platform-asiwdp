# MongoDB Flexible Attribute Collections

**Story:** Implement MongoDB flexible attribute collections  
**Epic:** Skills Framework & Competency Management Services  
**Project:** ASIWDP

## Purpose

Store optional, extensible skill/role metadata and audit blobs in MongoDB while
keeping normalized taxonomy entities in PostgreSQL. Every document is isolated
by `tenant_id` and stamped with an integer `version` aligned to the published
taxonomy revision.

## Collections

| Collection | Required keys | Flexible payload |
|------------|---------------|------------------|
| `skill_meta` | `tenant_id`, `skill_id`, `version` | `metadata`, `tags`, `audit_entries` |
| `role_meta` | `tenant_id`, `role_id`, `version` | `metadata`, `tags`, `audit_entries` |

JSON Schema validators (`db/mongodb/collections/*.validator.json`) reject
documents missing `tenant_id` / `version` (and the entity id). Unique compound
indexes enforce one meta document per `(tenant_id, skill_id|role_id, version)`.

## Data-access layer

Python package `asiwdp-skills-persistence` exposes:

- `ensure_meta_collections(db)` — idempotent create/collMod + indexes
- `SkillMetaRepository` / `RoleMetaRepository` — create, get, list, update,
  append_audit_entry, delete (always tenant-scoped)
