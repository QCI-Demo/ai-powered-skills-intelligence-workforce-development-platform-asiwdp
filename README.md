# AI-Powered Skills Intelligence & Workforce Development Platform (ASIWDP)

Multi-tenant SaaS foundation for skills intelligence and workforce development.

## Tenant Provisioning (this branch)

Automated, idempotent tenant provisioning with default configuration, PlatformAdmin
RBAC (Story S2 `asiwdp-auth` middleware), and tenant-scoped telemetry events.

| Area | Location |
| --- | --- |
| Design / ER | `docs/design/tenant-entity-schema.md` |
| PostgreSQL DDL | `db/postgres/sql/V1__create_tenant_provisioning_schema.sql` |
| MongoDB schemas | `db/mongodb/` |
| Service | `services/tenant-provisioning/` |
| API Gateway route | `config/api-gateway/tenant-provisioning-route.yaml` |
| OpenAPI | `openapi/tenant-provisioning-service.yaml` |
| Auth middleware (S2) | `libs/auth-middleware/` |
| RBAC matrix | `config/rbac/role-permission-matrix.yaml` |

### Run tests

```bash
pip install -e "libs/auth-middleware[dev]"
pip install -e "services/tenant-provisioning[dev]"
pytest services/tenant-provisioning/tests -q
```
