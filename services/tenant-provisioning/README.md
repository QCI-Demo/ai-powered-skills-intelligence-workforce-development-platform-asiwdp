# ASIWDP Tenant Provisioning Service

Automated tenant provisioning service for the AI-Powered Skills Intelligence & Workforce Development Platform.

## Features

- **Idempotent Tenant Creation**: Safe retries with `Idempotency-Key` header support
- **RBAC-Protected Endpoints**: Only `PlatformAdmin` can create new tenants
- **Default Configuration**: Automatic initialization with tier-based defaults
- **Event Publishing**: Tenant provisioning events emitted to telemetry bus
- **Audit Logging**: Complete audit trail for compliance

## API Endpoints

| Method | Path             | Description                    | Required Permission |
|--------|------------------|--------------------------------|---------------------|
| POST   | /api/tenants     | Provision a new tenant         | tenants:admin       |
| GET    | /api/tenants/:id | Get tenant details             | tenants:read        |
| GET    | /health          | Health check (unauthenticated) | -                   |

## Idempotency

All mutating endpoints support the `Idempotency-Key` header:

```bash
curl -X POST /api/tenants \
  -H "Authorization: Bearer <token>" \
  -H "Idempotency-Key: unique-request-id-123" \
  -H "Content-Type: application/json" \
  -d '{"name": "Acme Corp", "slug": "acme-corp", "contactEmail": "admin@acme.com"}'
```

If the same idempotency key is reused with identical request body, the service returns the original response.

## Configuration

| Environment Variable       | Default            | Description                    |
|---------------------------|--------------------|--------------------------------|
| DATABASE_URL              | -                  | PostgreSQL connection string   |
| AUTH_ISSUER               | -                  | JWT issuer URL                 |
| AUTH_AUDIENCE             | asiwdp-api         | Expected JWT audience          |
| AUTH_VERIFICATION_KEY     | -                  | JWT verification key/JWKS URL  |
| EVENT_BUS_URL             | -                  | Event bus endpoint             |
| IDEMPOTENCY_TTL_HOURS     | 24                 | Idempotency key expiration     |

## Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run service locally
uvicorn tenant_provisioning.app:app --reload
```

## Event Schema

Tenant provisioning events follow this schema:

```json
{
  "eventType": "tenant.provisioned",
  "eventId": "uuid",
  "timestamp": "2024-01-15T10:30:00Z",
  "tenantId": "uuid",
  "payload": {
    "name": "Acme Corp",
    "slug": "acme-corp",
    "tier": "standard",
    "createdBy": "user-uuid"
  }
}
```
