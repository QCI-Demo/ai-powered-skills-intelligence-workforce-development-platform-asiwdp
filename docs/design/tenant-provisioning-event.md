# Tenant Provisioning Event Schema

**Story:** Build Automated Tenant Provisioning and Configuration Service  
**Story ID:** `486d3e38-2cec-40cb-874d-576d2147732c`  
**Task:** Publish tenant provisioning event to telemetry (`4a9fb493-572e-4e33-bac6-eeb81ba43ec1`)

## 1. Purpose

After a tenant is created (not on idempotent replays that return an existing
tenant without re-creating), emit a structured, tenant-scoped event to the
centralized event bus so downstream services can initialize tenant context
(taxonomy seeds, metering, consent defaults, etc.).

## 2. Envelope

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `event_id` | string (UUID) | yes | Unique event id |
| `event_type` | string | yes | Constant `tenant.provisioned` |
| `event_version` | string | yes | Schema version (`1.0.0`) |
| `tenant_id` | string (UUID) | yes | **Partition / routing key** for the new tenant |
| `timestamp` | string (RFC 3339 UTC) | yes | When provisioning completed |
| `source` | string | yes | `asiwdp.tenant-provisioning` |
| `correlation_id` | string | no | Request / trace correlation |
| `actor` | object | yes | Who initiated provisioning |
| `payload` | object | yes | Provisioning details |

### Actor

| Field | Type | Description |
|-------|------|-------------|
| `subject` | string | JWT `sub` |
| `requesting_tenant_id` | string \| null | Tenant bound to the PlatformAdmin token |
| `roles` | string[] | Roles present on the token |

### Payload

| Field | Type | Description |
|-------|------|-------------|
| `slug` | string | Tenant slug |
| `display_name` | string | Human-readable name |
| `status` | string | Initial status (`active`) |
| `plan_code` | string | Commercial / entitlement plan |
| `region` | string | Deployment / residency region |
| `timezone` | string | Default timezone |
| `default_config_keys` | string[] | Keys seeded in default configuration |
| `idempotency_key` | string \| null | Client idempotency key if provided |
| `replay` | boolean | Always `false` for newly published create events |

## 3. Example

```json
{
  "event_id": "a1000000-0000-4000-8000-000000000001",
  "event_type": "tenant.provisioned",
  "event_version": "1.0.0",
  "tenant_id": "b2000000-0000-4000-8000-000000000002",
  "timestamp": "2026-08-31T09:30:00Z",
  "source": "asiwdp.tenant-provisioning",
  "correlation_id": "req_01EXAMPLE",
  "actor": {
    "subject": "11111111-1111-1111-1111-111111111111",
    "requesting_tenant_id": "22222222-2222-2222-2222-222222222222",
    "roles": ["platform_admin"]
  },
  "payload": {
    "slug": "acme-corp",
    "display_name": "Acme Corporation",
    "status": "active",
    "plan_code": "enterprise",
    "region": "us-east-1",
    "timezone": "America/New_York",
    "default_config_keys": [
      "locale",
      "timezone",
      "features.skills_framework",
      "features.recommendations",
      "features.learning_paths",
      "privacy.consent_required",
      "privacy.data_residency",
      "rbac.default_learner_role",
      "metering.usage_events_enabled"
    ],
    "idempotency_key": "prov-acme-001",
    "replay": false
  }
}
```

## 4. Bus contract

- Topic / subject: `asiwdp.tenants.provisioned`
- Partition key: `tenant_id` (guarantees tenant-scoped ordering)
- Delivery: at-least-once; consumers must be idempotent on `event_id` / `tenant_id`
