# Provisioning Endpoint Security

## Goal

Secure `POST /api/tenants` so only platform administrators can provision
tenants, using Story S2 OAuth2/JWT middleware and RBAC.

## Controls

1. **Authentication middleware (`asiwdp-auth`)**  
   Mounted by default on the tenant-provisioning FastAPI app. Validates Bearer
   JWTs (issuer, audience, signature, expiry). Health is public;
   provisioning is not.

2. **Role check (`PlatformAdmin`)**  
   Route dependency `require_platform_admin` accepts JWT roles
   `PlatformAdmin` or `platform_admin` (RBAC matrix alias). Tenant-scoped
   roles (`tenant_admin`, `learner`, …) are denied.

3. **HTTP outcomes**  
   - **401** — missing / invalid / expired token  
   - **403** — authenticated principal without PlatformAdmin  

## Fail-closed

Even if middleware is disabled (`ASIWDP_AUTH_ENABLED=false`), the route
dependency returns **401** when `request.state.principal` is absent.
