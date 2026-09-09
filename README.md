# AI-Powered Skills Intelligence & Workforce Development Platform (ASIWDP)

Multi-tenant SaaS platform foundation for skills intelligence, personalized
learning, and workforce readiness.

## Tenant Provisioning + Endpoint Security (this branch)

Idempotent `POST /api/tenants` creates a tenant record, seeds default
configuration and metadata, and emits a tenant-scoped provisioning event.
Security: Story S2 `AuthMiddleware` is mounted by default; only
`PlatformAdmin` / `platform_admin` may create tenants (HTTP **403** otherwise).

| Area | Location |
|------|----------|
| Design / ER | [`docs/design/tenant-entity-schema.md`](docs/design/tenant-entity-schema.md) |
| Provisioned event | [`docs/design/tenant-provisioned-event.md`](docs/design/tenant-provisioned-event.md) |
| PostgreSQL DDL | [`db/postgres/sql/V1__create_tenant_provisioning_schema.sql`](db/postgres/sql/V1__create_tenant_provisioning_schema.sql) |
| MongoDB schemas | [`db/mongodb/`](db/mongodb/) |
| Service | [`services/tenant-provisioning/`](services/tenant-provisioning/) |
| API Gateway route | [`config/api-gateway/tenant-provisioning-route.yaml`](config/api-gateway/tenant-provisioning-route.yaml) |
| OpenAPI | [`openapi/tenant-provisioning-service.yaml`](openapi/tenant-provisioning-service.yaml) |
| Auth middleware (S2) | [`libs/auth-middleware/`](libs/auth-middleware/) |
| RBAC matrix | [`config/rbac/role-permission-matrix.yaml`](config/rbac/role-permission-matrix.yaml) |

### Run provisioning tests

```bash
pip install -e "libs/auth-middleware[dev]"
pip install -e "services/tenant-provisioning[dev]"
pytest services/tenant-provisioning/tests -q
```

## OAuth2 / JWT Authentication Middleware

Reusable **`asiwdp-auth`** middleware library and supporting RBAC / OpenAPI
artifacts.

| Artifact | Path |
|----------|------|
| JWT claim schema & RBAC design | [`docs/design/jwt-claim-schema-and-rbac.md`](docs/design/jwt-claim-schema-and-rbac.md) |
| Role → permission matrix | [`config/rbac/role-permission-matrix.yaml`](config/rbac/role-permission-matrix.yaml) |
| Middleware package | [`libs/auth-middleware/`](libs/auth-middleware/) |
| Service OpenAPI specs | [`openapi/`](openapi/) |

### Install & test auth middleware

```bash
pip install -e "libs/auth-middleware[dev]"
pytest libs/auth-middleware/tests -q
```
