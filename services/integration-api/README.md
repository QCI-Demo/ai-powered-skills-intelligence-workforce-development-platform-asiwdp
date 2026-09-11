# ASIWDP Integration API Service

Secured, versioned REST endpoints for bidirectional exchange with HRIS, LMS,
and third-party content providers. JWT validation, tenant context extraction,
scope enforcement, and `X-API-Version` response headers are provided by the
shared `asiwdp-auth` middleware.

## Run tests

```bash
pip install -e "libs/auth-middleware[dev]"
pip install -e "services/integration-api[dev]"
pytest services/integration-api/tests -q
```

## Routes

| Version | Prefix | Controllers |
|---------|--------|-------------|
| v1 | `/api/v1` | `HrisV1Controller`, `LmsV1Controller`, `ContentV1Controller` |
| v2 | `/api/v2` | `HrisV2Controller`, `LmsV2Controller`, `ContentV2Controller` |

Required scopes: `hris:*`, `lms:*`, `content:*`, `integrations:credentials:rotate`.

Design: [`docs/design/api-versioning-and-scope-model.md`](../../docs/design/api-versioning-and-scope-model.md)
