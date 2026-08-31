# Tenant Provisioned Event Schema

**Story task:** `4a9fb493-572e-4e33-bac6-eeb81ba43ec1`

CloudEvents-inspired envelope. Always tenant-scoped via `tenantId` / `data.tenantId`.

```json
{
  "specversion": "1.0",
  "id": "evt-uuid",
  "type": "com.asiwdp.tenant.provisioned",
  "source": "asiwdp.tenant-provisioning",
  "time": "2026-08-31T08:00:00.000Z",
  "subject": "tenant/{tenantId}",
  "datacontenttype": "application/json",
  "tenantId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  "data": {
    "tenantId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    "slug": "acme-corp",
    "displayName": "Acme Corp",
    "status": "active",
    "planCode": "standard",
    "dataResidency": "us-east",
    "provisionedAt": "2026-08-31T08:00:00.000Z",
    "createdBy": "11111111-1111-1111-1111-111111111111",
    "requestingTenantId": "22222222-2222-2222-2222-222222222222",
    "configuration": {
      "locale": "en-US",
      "timezone": "UTC",
      "schemaVersion": 1,
      "meteringEnabled": true,
      "gdprEnabled": true,
      "ccpaEnabled": true
    },
    "idempotencyKey": "prov-key-001"
  }
}
```

## JSON Schema (validation)

See `services/tenant-provisioning/src/asiwdp_tenant_provisioning/events/tenant_provisioned.schema.json`.

## Bus routing

- Topic / channel: `asiwdp.telemetry.tenant-events`
- Partition key: `tenantId` (ensures ordered delivery per tenant)
