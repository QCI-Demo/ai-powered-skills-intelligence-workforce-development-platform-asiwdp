# ASIWDP MongoDB — Tenant Provisioning Collections

Collections for tenant documents, default configuration, and tenant-scoped
metadata. Every document requires `tenant_id` as the partition key.

| Collection | Validator | Indexes |
|------------|-----------|---------|
| `tenants` | [`collections/tenant.validator.json`](collections/tenant.validator.json) | unique `tenant_id`, unique `slug` |
| `tenant_configurations` | [`collections/tenant_configuration.validator.json`](collections/tenant_configuration.validator.json) | unique `(tenant_id, config_key)` |
| `tenant_metadata` | [`collections/tenant_metadata.validator.json`](collections/tenant_metadata.validator.json) | unique `(tenant_id, meta_key)` |

```bash
mongosh "$MONGODB_URI" db/mongodb/init/create_tenant_collections.js
```
