# ASIWDP OpenAPI Specifications

Service OpenAPI documents with OAuth2 Bearer JWT security schemes and
tenant-scoped RBAC scope annotations.

| File | Service |
|------|---------|
| `skills-framework-service.yaml` | Skills, categories, proficiency, import/export |
| `recommendation-engine-service.yaml` | AI recommendations |
| `learning-path-service.yaml` | Learning paths |
| `progress-tracking-service.yaml` | Progress tracking |
| `analytics-insights-service.yaml` | Analytics & insights |
| `tenant-admin-service.yaml` | Tenant / org / user admin |
| `portal/` | Staged copies published for the API portal |

All protected operations declare `security` referencing `OAuth2Bearer` and
document required scopes (e.g. `skills:write`). Claim schema:
`docs/design/jwt-claim-schema-and-rbac.md`.

## Skills Framework (versioned CRUD + bulk pipelines)

`skills-framework-service.yaml` defines OpenAPI v3 entries for:

- Version-aware CRUD for **skills**, **categories**, and **proficiency levels**
  (create, read, update, retire, list, search)
- `X-Taxonomy-Version` header and `version` query parameters
- Tenant-scoped OAuth2 security scopes (`skills:read` / `skills:write` / …)
- Bulk CSV/JSON/NDJSON import (`POST /taxonomy/import`) with row-level reports
- Streaming taxonomy export (`GET /taxonomy/export`) for current/historic snapshots

## Lint & publish

```bash
pip install "openapi-spec-validator>=0.7.0" PyYAML
# optional local Spectral CLI
(cd tools/openapi-lint && npm install)
./scripts/validate_and_publish_openapi.sh
```

External production portal deploy is withheld for human owner approval; this
script stages documents under `openapi/portal/`.
