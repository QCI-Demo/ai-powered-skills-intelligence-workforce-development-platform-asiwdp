# ASIWDP Tenant Provisioning Service

Idempotent `POST /api/tenants` that creates a tenant record, seeds default
configuration and metadata, enforces **PlatformAdmin** RBAC via Story S2
`asiwdp-auth` middleware, and publishes a tenant-scoped provisioning event to
the centralized telemetry event bus (`asiwdp.telemetry.tenant-events`).

## Telemetry

After a **successful first-time create**, the service emits
`com.asiwdp.tenant.provisioned` with:

* `tenantId` (envelope + payload) — tenant isolation / bus partition key
* `time` / `data.timestamp` — UTC provisioning timestamp
* provisioning details — slug, plan, residency, default configuration, etc.

Idempotent replays do **not** emit a second event. Schema:
`contracts/telemetry/v1/tenant-provisioned.schema.json`.

## Security (Story S2 middleware + RBAC)

| Layer | Behavior |
| --- | --- |
| `AuthMiddleware` | Validates Bearer JWT; mounts **by default** (`ASIWDP_AUTH_ENABLED` defaults to `true`) |
| `require_platform_admin` | Route dependency: **401** if unauthenticated, **403** without `PlatformAdmin` / `platform_admin` |
| Public paths | `GET /api/tenants/health` only |

Only platform administrators may provision tenants. Tenant-scoped roles such as
`tenant_admin` or `learner` receive **HTTP 403**.

## Quick start

```bash
pip install -e "libs/auth-middleware[dev]"
pip install -e "services/tenant-provisioning[dev]"
uvicorn asiwdp_tenant_provisioning.app:app --reload
```

Disable auth only for local scaffolding:

```bash
ASIWDP_AUTH_ENABLED=false uvicorn asiwdp_tenant_provisioning.app:app --reload
```

(Route-level PlatformAdmin check still returns 401 without a principal.)

## Endpoints

| Method | Path | Auth |
| --- | --- | --- |
| `POST` | `/api/tenants` | Bearer JWT + `PlatformAdmin` / `platform_admin` |
| `GET` | `/api/tenants/health` | Public |

Headers: `Authorization`, `Idempotency-Key` (required for create).
