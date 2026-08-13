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

## Lint & publish

```bash
pip install "openapi-spec-validator>=0.7.0" PyYAML
./scripts/validate_and_publish_openapi.sh
```

The skills framework spec includes `X-Taxonomy-Version`, tenant security scopes,
CRUD/search/retire schemas, `/taxonomy/import`, and streaming `/taxonomy/export`.
