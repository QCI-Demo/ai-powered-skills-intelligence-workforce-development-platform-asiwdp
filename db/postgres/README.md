# PostgreSQL — Tenant Provisioning

Flyway/Liquibase-compatible SQL for the tenant registry, default configuration,
metadata, and idempotency store.

| Migration | Purpose |
| --- | --- |
| `sql/V1__create_tenant_provisioning_schema.sql` | Tenant, configuration, metadata, idempotency |

All tenant-owned tables carry `tenant_id` as the isolation / partition key.
