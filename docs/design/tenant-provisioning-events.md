# Tenant Provisioning Events

This document describes the events emitted by the tenant provisioning service.

## Event: tenant.provisioned

Emitted when a new tenant is successfully created and provisioned.

**Task:** 4a9fb493-572e-4e33-bac6-eeb81ba43ec1

### Schema

```json
{
  "eventType": "tenant.provisioned",
  "eventId": "uuid",
  "timestamp": "2024-01-15T10:30:00Z",
  "tenantId": "uuid",
  "tenantSlug": "string",
  "tenantName": "string",
  "createdBy": "string",
  "configurationVersion": 1,
  "metadata": {
    "key": "value"
  }
}
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| eventType | string | Always `"tenant.provisioned"` |
| eventId | uuid | Unique identifier for this event |
| timestamp | datetime | ISO 8601 timestamp when event was generated |
| tenantId | uuid | Unique identifier of the created tenant |
| tenantSlug | string | URL-safe slug of the tenant |
| tenantName | string | Display name of the tenant |
| createdBy | string | Subject ID of the user who created the tenant |
| configurationVersion | integer | Version of the tenant configuration |
| metadata | object | Key-value metadata associated with the tenant |

### Headers

When published via HTTP:

| Header | Value |
|--------|-------|
| Content-Type | application/json |
| X-Event-Type | tenant.provisioned |
| X-Tenant-Id | {tenantId} |

### Subscribers

Downstream services that should handle this event:

1. **Billing Service** - Initialize billing records for the tenant
2. **Analytics Service** - Set up analytics tracking
3. **Notification Service** - Send welcome notifications
4. **Audit Service** - Log provisioning action

### Example

```json
{
  "eventType": "tenant.provisioned",
  "eventId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "tenantId": "550e8400-e29b-41d4-a716-446655440000",
  "tenantSlug": "acme-corp",
  "tenantName": "Acme Corp",
  "createdBy": "platform-admin-user",
  "configurationVersion": 1,
  "metadata": {
    "industry": "Technology",
    "region": "us-west-2"
  }
}
```

### Event Bus Configuration

The event is published to the configured `EVENT_BUS_URL` endpoint. Recommended configurations:

- **Development**: Log events to stdout
- **Production**: Apache Kafka topic `tenant-events` or AWS EventBridge
