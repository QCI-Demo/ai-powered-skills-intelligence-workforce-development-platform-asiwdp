# MongoDB — Tenant Provisioning Collections

| Collection | Partition key | Validator |
| --- | --- | --- |
| `tenants` | `tenant_id` | `collections/tenants.validator.json` |
| `tenant_configurations` | `tenant_id` | `collections/tenant_configurations.validator.json` |
| `tenant_metadata` | `tenant_id` | `collections/tenant_metadata.validator.json` |
| `idempotency_records` | `tenant_id` | `collections/idempotency_records.validator.json` |

Initialize:

```bash
mongosh "$MONGODB_URI" db/mongodb/init/create_tenant_collections.js
```
