# ASIWDP Tenant Provisioning Service

Idempotent `POST /api/tenants` that creates a tenant record, seeds default
configuration and metadata, enforces **PlatformAdmin** RBAC via Story S2
`asiwdp-auth` middleware, and emits a tenant-scoped provisioning event.

## Quick start

```bash
pip install -e "libs/auth-middleware[dev]"
pip install -e "services/tenant-provisioning[dev]"
ASIWDP_AUTH_ENABLED=true uvicorn asiwdp_tenant_provisioning.app:app --reload
```

## Endpoints

| Method | Path | Auth |
| --- | --- | --- |
| `POST` | `/api/tenants` | Bearer JWT + `PlatformAdmin` / `platform_admin` |
| `GET` | `/api/tenants/health` | Public |

Headers: `Authorization`, `Idempotency-Key` (required for create).
