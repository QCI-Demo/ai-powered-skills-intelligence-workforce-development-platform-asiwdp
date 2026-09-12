# Tenant Provisioned Event Schema

**Story task:** Publish tenant provisioning event to telemetry

CloudEvents-inspired envelope published to the **centralized telemetry event
bus** after a successful first-time tenant create. Always tenant-scoped via
`tenantId` / `data.tenantId` / bus `partition_key`.

## Required fields

| Field | Location | Purpose |
| --- | --- | --- |
| `tenantId` | envelope + `data` | Tenant isolation / routing key |
| `time` / `data.timestamp` | envelope + `data` | UTC provisioning timestamp |
| provisioning details | `data` | slug, plan, residency, configuration, etc. |

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
    "timestamp": "2026-08-31T08:00:00.000Z",
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

- Canonical contract: `contracts/telemetry/v1/tenant-provisioned.schema.json`
- Runtime embed: `services/tenant-provisioning/src/asiwdp_tenant_provisioning/events/tenant_provisioned.schema.json`

## Publish lifecycle

1. Persist tenant + default configuration + metadata (idempotent store).
2. **Only when `created=true`** (first successful create), build and validate
   the event against the schema.
3. Publish to the centralized bus with `partition_key = tenantId`.
4. Idempotent replays (`created=false`) must **not** emit a second event.

## Bus routing

- Topic / channel: `asiwdp.telemetry.tenant-events`
- Partition key: `tenantId` (ordered delivery per tenant)
- Subject: `tenant/{tenantId}`
