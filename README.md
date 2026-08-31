# AI-Powered Skills Intelligence & Workforce Development Platform (ASIWDP)

Multi-tenant SaaS platform foundation for skills intelligence, personalized
learning, and workforce readiness.

## Tenant Provisioning Service

Story `486d3e38-2cec-40cb-874d-576d2147732c` delivers idempotent tenant
provisioning with default configuration, PlatformAdmin RBAC, and telemetry
events.

| Artifact | Path |
|----------|------|
| Entity schema / ER | [`docs/design/tenant-entity-schema.md`](docs/design/tenant-entity-schema.md) |
| Provisioning event | [`docs/design/tenant-provisioning-event.md`](docs/design/tenant-provisioning-event.md) |
| PostgreSQL DDL | [`db/postgres/sql/V1__create_tenant_schema.sql`](db/postgres/sql/V1__create_tenant_schema.sql) |
| MongoDB collections | [`db/mongodb/`](db/mongodb/) |
| Service | [`services/tenant-provisioning/`](services/tenant-provisioning/) |
| Gateway route | [`gateway/routes/tenant-provisioning.yaml`](gateway/routes/tenant-provisioning.yaml) |
| OpenAPI | [`openapi/tenant-provisioning-service.yaml`](openapi/tenant-provisioning-service.yaml) |
| Auth middleware (S2) | [`libs/auth-middleware/`](libs/auth-middleware/) |

### Install & test

```bash
pip install -e "libs/auth-middleware[dev]"
pip install -e "services/tenant-provisioning[dev]"
pytest services/tenant-provisioning/tests -q
pytest libs/auth-middleware/tests -q
```

### Endpoint

`POST /api/tenants` — PlatformAdmin only; supports `Idempotency-Key`.
