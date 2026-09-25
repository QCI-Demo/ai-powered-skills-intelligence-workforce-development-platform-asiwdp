# ASIWDP Tenant Provisioning Service

Automated tenant provisioning and configuration service for the AI-Powered 
Skills Intelligence & Workforce Development Platform (ASIWDP).

## Features

- **Idempotent Provisioning**: Create tenants with replay protection via
  `Idempotency-Key` header
- **Default Configuration**: Tier-based configuration initialization
- **RBAC Protection**: PlatformAdmin role required for tenant creation
- **Event Telemetry**: Provisioning events emitted to centralized event bus

## Story Reference

- **Story**: Build Automated Tenant Provisioning and Configuration Service
- **Story ID**: `486d3e38-2cec-40cb-874d-576d2147732c`
- **Epic**: Multi-Tenant SaaS Platform Foundation

## API Endpoints

### POST /api/tenants

Create a new tenant with default configuration.

**Headers:**
- `Authorization: Bearer <access_token>` (required)
- `Idempotency-Key: <unique-key>` (optional, for replay protection)
- `X-Correlation-ID: <trace-id>` (optional, for distributed tracing)

**Request Body:**
```json
{
  "name": "Acme Corporation",
  "slug": "acme-corp",
  "display_name": "Acme Corp",
  "tier": "professional",
  "contact_email": "admin@acme.example.com",
  "owner_user_id": "uuid",
  "metadata": {}
}
```

**Response (201 Created):**
```json
{
  "tenant": {
    "tenant_id": "uuid",
    "name": "Acme Corporation",
    "slug": "acme-corp",
    "status": "active",
    "tier": "professional",
    ...
  },
  "idempotent": false,
  "message": "Tenant provisioned successfully"
}
```

### GET /api/tenants/{tenant_id}

Retrieve tenant details. Requires `tenants:read` permission.

### GET /health

Liveness probe (no authentication required).

## Installation

```bash
# Install with development dependencies
pip install -e "services/tenant-provisioning[dev]"

# Install with PostgreSQL support
pip install -e "services/tenant-provisioning[postgres]"

# Install with MongoDB support
pip install -e "services/tenant-provisioning[mongodb]"
```

## Configuration

Environment variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `ASIWDP_AUTH_ISSUER` | JWT issuer URL | Yes |
| `ASIWDP_AUTH_AUDIENCE` | JWT audience | Yes |
| `ASIWDP_AUTH_VERIFICATION_KEY` | JWT verification key | Yes |
| `ASIWDP_EVENT_BUS_URL` | Event bus URL | No |
| `DATABASE_URL` | PostgreSQL connection string | For production |
| `MONGODB_URL` | MongoDB connection string | For MongoDB mode |

## Running

```bash
# Development
uvicorn services.tenant_provisioning.src.main:app --reload

# Production
uvicorn services.tenant_provisioning.src.main:app --host 0.0.0.0 --port 8000
```

## Testing

```bash
# Run all tests
pytest services/tenant-provisioning/tests -v

# Run with coverage
pytest services/tenant-provisioning/tests --cov=services/tenant_provisioning

# Run specific test class
pytest services/tenant-provisioning/tests -v -k "TestTenantProvisioning"
```

## Database Schemas

See `db/migrations/` for:
- `001_tenant_provisioning_schema.sql` - PostgreSQL DDL
- `001_tenant_provisioning_mongodb.js` - MongoDB collection schema

## Events

Provisioning events emitted:

| Event Type | Description |
|------------|-------------|
| `tenant.provisioning.started` | Provisioning initiated |
| `tenant.provisioning.completed` | Provisioning successful |
| `tenant.provisioning.failed` | Provisioning failed |
| `tenant.configuration.initialized` | Default config applied |

Events follow CloudEvents 1.0 specification and include:
- `tenant_id` for scoping
- `correlation_id` for tracing
- Timestamp in ISO 8601 format

## Authorization

| Endpoint | Required Permission |
|----------|---------------------|
| POST /api/tenants | `platform_admin` role or `tenants:admin` permission |
| GET /api/tenants/{id} | `tenants:read` permission |

See `config/rbac/role-permission-matrix.yaml` for role definitions.
