# ASIWDP Tenant Provisioning Service

Automated tenant provisioning service with idempotent REST endpoints for creating tenant records,
initializing default configuration, and storing tenant-scoped metadata.

## Features

- **Idempotent Provisioning**: POST /api/tenants with Idempotency-Key header support
- **RBAC Security**: Protected by authentication middleware from Story S2
- **Platform Admin Only**: Only users with `platform_admin` role can create tenants
- **Event Emission**: Publishes `tenant.provisioned` events for downstream services
- **Atomic Operations**: Tenant and configuration created in a single transaction

## API Endpoints

### POST /api/tenants

Creates a new tenant with default configuration.

**Headers:**
- `Authorization: Bearer <jwt>` - Required, must have `platform_admin` role
- `Idempotency-Key: <uuid>` - Recommended, ensures safe retries

**Request Body:**
```json
{
  "name": "Acme Corp",
  "slug": "acme-corp",
  "metadata": {
    "industry": "Technology",
    "region": "us-west-2"
  }
}
```

**Response (201 Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Acme Corp",
  "slug": "acme-corp",
  "status": "active",
  "configuration": { ... },
  "createdAt": "2024-01-15T10:30:00Z"
}
```

### GET /health

Liveness probe endpoint (unauthenticated).

## Environment Variables

- `DATABASE_URL`: PostgreSQL connection string
- `JWT_ISSUER`: Expected JWT issuer
- `JWT_AUDIENCE`: Expected JWT audience
- `JWKS_URL`: URL to fetch JWKS for JWT verification
- `EVENT_BUS_URL`: Event bus endpoint for publishing events

## Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run service
uvicorn tenant_provisioning.app:app --reload
```
