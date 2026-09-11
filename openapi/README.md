# ASIWDP OpenAPI Specifications

Service OpenAPI documents with OAuth2 Bearer JWT security schemes and
tenant-scoped RBAC scope annotations.

| File | Service |
|------|---------|
| `skills-framework-service.yaml` | Skills & competencies |
| `recommendation-engine-service.yaml` | AI recommendations |
| `learning-path-service.yaml` | Learning paths |
| `progress-tracking-service.yaml` | Progress tracking |
| `analytics-insights-service.yaml` | Analytics & insights |
| `tenant-admin-service.yaml` | Tenant / org / user admin |
| `integration-api-service.yaml` | HRIS / LMS / content Integration APIs (v1/v2) |

All protected operations declare `security` referencing `OAuth2Bearer` and
document required scopes (e.g. `skills:write`, `hris:write`). Claim schema:
`docs/design/jwt-claim-schema-and-rbac.md`. Versioning:
`docs/design/api-versioning-and-scope-model.md`.
