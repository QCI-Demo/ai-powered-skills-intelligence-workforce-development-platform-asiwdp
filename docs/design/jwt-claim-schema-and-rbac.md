# ASIWDP JWT Claim Schema and Tenant-Scoped RBAC

**Story:** Implement OAuth2/JWT Authentication Middleware and Tenant-Scoped RBAC  
**Story ID:** `6db721b1-7e99-4f99-992e-2bfda2e66a84`  
**Task:** Design JWT claim schema and RBAC matrix (`d7333b8d-46fe-4ad3-8e12-61e4c5871c35`)  
**Aligned with:** EIAMS `TokenClaims` / `RequestContext` contracts

## 1. Purpose

Define the canonical access-token claim structure and the role-to-permission
matrix used by the reusable `asiwdp-auth` middleware. Every protected
micro-service must validate tokens against this schema and enforce
tenant-scoped RBAC before executing business logic.

## 2. Token Type and Transport

| Aspect | Value |
|--------|--------|
| Token type | OAuth 2.0 Bearer access token (JWT) |
| Header | `Authorization: Bearer <access_token>` |
| Algorithm | RS256 (asymmetric) in production; HS256 allowed for local tests only |
| Issuer (`iss`) | Platform identity service (EIAMS) issuer URL |
| Audience (`aud`) | `asiwdp-api` (or service-specific audience list) |
| Clock skew | ≤ 60 seconds |

Fail-closed behavior: missing, expired, signature-invalid, or claim-incomplete
tokens are rejected with **401 Unauthorized**. Authenticated principals that
lack the required permission for the requested operation receive
**403 Forbidden**.

## 3. Canonical Claim Schema

Claims use snake_case to align with EIAMS `TokenClaims`. The middleware also
accepts camelCase aliases (`tenantId`, `sessionId`) for interoperability and
normalizes them at verification time.

### 3.1 Required claims

| Claim | Type | Description |
|-------|------|-------------|
| `sub` | string (UUID) | Subject / user or service principal ID |
| `tenant_id` | string (UUID) | Tenant boundary for data isolation |
| `iat` | integer (epoch seconds) | Issued-at |
| `exp` | integer (epoch seconds) | Expiration |
| `iss` | string (URI) | Token issuer |
| `aud` | string or string[] | Intended audience |
| `roles` | string[] | Tenant-scoped role names |
| `scopes` | string[] | OAuth2 scopes / permission keys (`resource:action`) |

### 3.2 Optional claims

| Claim | Type | Description |
|-------|------|-------------|
| `session_id` | string (UUID) | Authenticated session identifier |
| `permissions` | string[] | Explicit effective permissions (may mirror or extend `scopes`) |
| `org_id` | string (UUID) | Optional organization scope within the tenant |
| `actor_type` | string | `user` \| `service` \| `system` (default `user`) |
| `jti` | string | Unique token ID (replay protection / audit) |
| `azp` | string | Authorized party (OAuth client ID) |

### 3.3 Example access token payload

```json
{
  "sub": "11111111-1111-1111-1111-111111111111",
  "tenant_id": "22222222-2222-2222-2222-222222222222",
  "session_id": "33333333-3333-3333-3333-333333333333",
  "iat": 1786450800,
  "exp": 1786454400,
  "iss": "https://auth.asiwdp.example/",
  "aud": "asiwdp-api",
  "actor_type": "user",
  "org_id": "44444444-4444-4444-4444-444444444444",
  "roles": ["skills_manager", "learner"],
  "scopes": [
    "skills:read",
    "skills:write",
    "competencies:read",
    "learning_paths:read",
    "progress:read",
    "progress:write"
  ],
  "jti": "tok_01HXYZEXAMPLE"
}
```

### 3.4 Effective permissions

Effective permissions for a request are the **union** of:

1. Token `scopes`
2. Token `permissions` (if present)
3. Permissions implied by each role in `roles` via
   `config/rbac/role-permission-matrix.yaml`

Platform-level `*` (wildcard) is reserved for `platform_admin` /
`system` actors and must never appear on learner or customer-admin tokens
unless explicitly issued by the identity service for break-glass operations.

## 4. Role Catalog

| Role | Tenant scope | Intent |
|------|--------------|--------|
| `platform_admin` | Cross-tenant | Platform operations (break-glass) |
| `tenant_admin` | Single tenant | Full tenant administration |
| `org_admin` | Tenant + org | Organization administration |
| `skills_manager` | Tenant | Skills framework & competency management |
| `learning_designer` | Tenant | Learning path design |
| `analyst` | Tenant | Workforce analytics (read) |
| `manager` | Tenant | Team readiness insights |
| `learner` | Tenant | Personalized learning & progress |
| `service_account` | Tenant | Machine-to-machine integrations |

## 5. Service-Level Permission Keys

Permission keys follow `resource_type:action` (aligned with EIAMS
`Permission.permission_key`).

| Service | Resource types | Actions |
|---------|----------------|---------|
| Skills Framework | `skills`, `competencies` | `read`, `write`, `delete`, `admin` |
| Recommendation Engine | `recommendations` | `read`, `generate`, `admin` |
| Learning Path | `learning_paths` | `read`, `write`, `assign`, `delete`, `admin` |
| Progress Tracking | `progress` | `read`, `write`, `admin` |
| Analytics / Insights | `analytics` | `read`, `export`, `admin` |
| Tenant Admin / IAM edge | `tenants`, `users`, `organizations`, `roles` | `read`, `write`, `delete`, `admin` |
| Privacy / Consent | `consent` | `read`, `write`, `admin` |
| Usage Metering | `usage` | `read`, `write`, `admin` |

Full role → permission mappings live in
[`config/rbac/role-permission-matrix.yaml`](../../config/rbac/role-permission-matrix.yaml).

## 6. Middleware Enforcement Contract

1. Extract Bearer token from `Authorization`.
2. Verify signature, `iss`, `aud`, `exp` / `iat` (with skew).
3. Require `sub` and `tenant_id` (fail closed).
4. Build request principal: subject, tenant, roles, scopes, effective permissions.
5. Optionally enforce a required permission / scope for the route.
6. Attach principal to request state for downstream handlers.
7. Never log raw tokens or secrets.

HTTP outcomes:

| Condition | Status |
|-----------|--------|
| Missing / malformed Authorization | 401 |
| Invalid signature / tampered token | 401 |
| Expired token | 401 |
| Missing required claims | 401 |
| Wrong issuer / audience | 401 |
| Authenticated but permission denied | 403 |

## 7. Tenant Isolation Rules

- Every protected operation runs inside the token’s `tenant_id`.
- Path / query / body tenant identifiers must match the token tenant or the
  request is denied (403).
- `platform_admin` may operate cross-tenant only when the identity service
  issues a token without a binding tenant **and** the calling service
  explicitly opts into platform mode (default is tenant-required).

## 8. OpenAPI Mapping

Services declare:

```yaml
components:
  securitySchemes:
    OAuth2Bearer:
      type: http
      scheme: bearer
      bearerFormat: JWT
security:
  - OAuth2Bearer: []
```

Per-endpoint `security` / description documents the required scopes
(e.g. `skills:write`). See files under [`openapi/`](../../openapi/).

## 9. Versioning

| Field | Value |
|-------|--------|
| Schema version | `1.0.0` |
| Matrix file | `config/rbac/role-permission-matrix.yaml` |
| Package | `asiwdp-auth` (`libs/auth-middleware`) |
