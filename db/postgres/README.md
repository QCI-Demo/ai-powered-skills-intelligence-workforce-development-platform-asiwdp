# ASIWDP PostgreSQL — Tenant Schema

Flyway-style migrations for the tenant provisioning service.

| Version | File | Description |
|---------|------|-------------|
| V1 | [`sql/V1__create_tenant_schema.sql`](sql/V1__create_tenant_schema.sql) | `tenant`, `tenant_configuration`, `tenant_metadata`, `idempotency_record` |

All tenant-scoped tables include `tenant_id` as the isolation / partition key.
