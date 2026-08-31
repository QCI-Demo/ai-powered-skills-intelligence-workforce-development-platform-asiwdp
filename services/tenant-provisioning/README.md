# ASIWDP Tenant Provisioning Service

Idempotent REST API that creates tenant records, seeds default configuration,
stores tenant-scoped metadata, enforces PlatformAdmin RBAC via `asiwdp-auth`,
and emits `tenant.provisioned` events.

| Concern | Location |
|---------|----------|
| Design / ER | [`docs/design/tenant-entity-schema.md`](../../docs/design/tenant-entity-schema.md) |
| Event schema | [`docs/design/tenant-provisioning-event.md`](../../docs/design/tenant-provisioning-event.md) |
| PostgreSQL DDL | [`db/postgres/sql`](../../db/postgres/sql) |
| MongoDB | [`db/mongodb`](../../db/mongodb) |
| Gateway route | [`gateway/routes/tenant-provisioning.yaml`](../../gateway/routes/tenant-provisioning.yaml) |
| OpenAPI | [`openapi/tenant-provisioning-service.yaml`](../../openapi/tenant-provisioning-service.yaml) |

## Install & test

```bash
pip install -e "libs/auth-middleware[dev]"
pip install -e "services/tenant-provisioning[dev]"
pytest services/tenant-provisioning/tests -q
```

## Endpoint

`POST /api/tenants`

- Requires Bearer JWT with role `PlatformAdmin` / `platform_admin`
- Optional `Idempotency-Key` header for safe retries
- Atomically persists tenant + default configuration + metadata
- Publishes a tenant-scoped `tenant.provisioned` event on first create
