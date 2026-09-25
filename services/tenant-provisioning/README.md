# Tenant Provisioning Service

Idempotent REST endpoints for automated tenant provisioning with default configuration and event publishing.

## Overview

This service provides:

- **POST /api/tenants** - Create a new tenant with default configuration
- **GET /api/tenants/{tenant_id}** - Retrieve tenant details
- **GET /api/tenants/{tenant_id}/configurations** - List tenant configurations

## Features

- **Idempotent Provisioning**: Use `Idempotency-Key` header for safe retries
- **Default Configuration**: Automatic tier-based configuration initialization
- **RBAC Enforcement**: Platform admin role required for tenant creation
- **Event Publishing**: Emits `tenant.provisioned` events for downstream services
- **Audit Logging**: Complete audit trail for compliance

## Authentication & Authorization

The service integrates with the `asiwdp-auth` middleware from Story S2:

- All endpoints require valid JWT authentication
- Tenant creation requires `PlatformAdmin` role or `tenants:admin` permission
- Read operations require `tenants:read` permission

## Quick Start

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Start service
TENANT_PROVISIONING_DATABASE_URL=postgresql+asyncpg://... tenant-provisioning
```

## API Usage

### Create Tenant

```bash
curl -X POST http://localhost:8080/api/tenants \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: unique-key-123" \
  -d '{
    "name": "acme-corp",
    "display_name": "Acme Corporation",
    "plan_tier": "professional",
    "metadata": {"industry": "technology"}
  }'
```

### Response

```json
{
  "tenant": {
    "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "acme-corp",
    "display_name": "Acme Corporation",
    "status": "active",
    "plan_tier": "professional",
    "provisioned_at": "2024-01-15T10:30:00Z"
  },
  "configurations": [
    {
      "config_key": "max_users",
      "config_value": 500,
      "category": "general"
    }
  ],
  "idempotent": false
}
```

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `TENANT_PROVISIONING_DATABASE_URL` | `postgresql+asyncpg://...` | Database connection string |
| `TENANT_PROVISIONING_JWT_ISSUER` | `https://auth.asiwdp.example` | Expected JWT issuer |
| `TENANT_PROVISIONING_IDEMPOTENCY_TTL_HOURS` | `24` | Idempotency key TTL |
| `TENANT_PROVISIONING_EVENT_BUS_TOPIC` | `tenant-provisioning-events` | Event bus topic |

## Event Schema

Provisioning events follow this schema:

```json
{
  "event_id": "uuid",
  "event_type": "tenant.provisioned",
  "tenant_id": "uuid",
  "tenant_name": "string",
  "plan_tier": "string",
  "created_by": "string",
  "timestamp": "ISO8601",
  "metadata": {}
}
```

## Database Schema

See [docs/design/schemas/tenant-provisioning-erd.md](../../docs/design/schemas/tenant-provisioning-erd.md) for the entity-relationship diagram and DDL files.
