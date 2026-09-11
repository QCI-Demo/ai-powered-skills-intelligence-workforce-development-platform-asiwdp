# ASIWDP API Versioning and Scope Model

**Story:** Implement Secured Versioned Integration APIs and Credential Controls  
**Epic:** Integration APIs, Ingestion Pipelines & Event Webhooks  
**Aligned with:** Story 001 contracts + `asiwdp-auth` JWT claim schema

## 1. Purpose

Define how Integration APIs for HRIS, LMS, and content providers are versioned,
authenticated, and authorized. Every secured endpoint must:

1. Verify an OAuth2 Bearer JWT (PyJWT via `asiwdp-auth`)
2. Map claims to a request-scoped `TenantContext` (`tenant_id` + `scopes`)
3. Enforce resource scopes (`hris:*`, `lms:*`, `content:*`, `integrations:*`)
4. Return the negotiated API version on every response via `X-API-Version`

## 2. Versioning

| Mechanism | Behavior |
|-----------|----------|
| Path prefix | `/api/v1/...` and `/api/v2/...` (preferred) |
| Request header | Optional `X-API-Version: v1\|v2` when path is unversioned |
| Response header | **Always** return `X-API-Version` (resolved version) |

### Version semantics

| Version | Contract |
|---------|----------|
| `v1` | Stable Story 001 envelopes — single-record exchange, basic acknowledgements |
| `v2` | Additive enhancements — batch ingest, correlation IDs, processing status links |

Breaking changes require a new major path (`/api/v3`). Additive fields stay in-place.

Middleware: `ApiVersionMiddleware` (`libs/auth-middleware`).

## 3. Scope catalog (Integration APIs)

| Scope | Intent |
|-------|--------|
| `hris:read` / `hris:write` | Employee & role sync (HRIS) |
| `lms:read` / `lms:write` | Learner activity & enrollments (LMS) |
| `content:read` / `content:write` | Third-party content catalog exchange |
| `integrations:read` / `integrations:write` | Connector metadata |
| `integrations:credentials:rotate` | Secret-manager credential rotation |
| `integrations:admin` | Full integration administration |

Scopes appear on the JWT `scopes` claim (or space-delimited `scope`) and are
unioned with RBAC role permissions into `Principal.effective_permissions`.

## 4. Middleware pipeline

```
Request
  │
  ▼
ApiVersionMiddleware          resolve version → stamp X-API-Version
  │
  ▼
AuthMiddleware (PyJWT)        verify sig/iss/aud/exp → Principal
  │
  ▼
TenantContext mapping         tenant_id + scopes on request.state
  │
  ▼
require_scope / controller    enforce scope; bind tenant isolation
  │
  ▼
Handler / controller class
```

Fail-closed HTTP outcomes match the JWT design doc (401 authn / 403 authz).

## 5. Controllers

| Class | Base path | Notes |
|-------|-----------|-------|
| `HrisV1Controller` | `/api/v1/hris` | Single-record employee/role exchange |
| `LmsV1Controller` | `/api/v1/lms` | Learner activity ingest / content list |
| `ContentV1Controller` | `/api/v1/content` | Catalog push/pull |
| `HrisV2Controller` | `/api/v2/hris` | Batch + status |
| `LmsV2Controller` | `/api/v2/lms` | Batch activities |
| `ContentV2Controller` | `/api/v2/content` | Batch catalog upsert |

## 6. Credential controls (boundary)

Integration credentials are referenced by opaque `credentialRef` identifiers.
Rotation requires `integrations:credentials:rotate`. Secrets are never logged,
returned in API bodies, or committed to source control — only secret-manager
handles hold raw material.

## 7. Artifacts

| Artifact | Path |
|----------|------|
| Auth + version middleware | `libs/auth-middleware/` |
| Integration service | `services/integration-api/` |
| OpenAPI | `openapi/integration-api-service.yaml` |
| RBAC matrix | `config/rbac/role-permission-matrix.yaml` |
