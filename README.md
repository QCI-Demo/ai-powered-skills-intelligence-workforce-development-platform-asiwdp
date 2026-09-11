# AI-Powered Skills Intelligence & Workforce Development Platform (ASIWDP)

Multi-tenant SaaS platform foundation for skills intelligence, personalized
learning, and workforce readiness.

## Secured Versioned Integration APIs

Story delivery for secured, tenant-scoped Integration APIs (HRIS / LMS /
content) with JWT validation, scope enforcement, and `X-API-Version` headers.

| Artifact | Path |
|----------|------|
| API versioning & scope design | [`docs/design/api-versioning-and-scope-model.md`](docs/design/api-versioning-and-scope-model.md) |
| Integration service | [`services/integration-api/`](services/integration-api/) |
| OpenAPI | [`openapi/integration-api-service.yaml`](openapi/integration-api-service.yaml) |
| Auth + version middleware | [`libs/auth-middleware/`](libs/auth-middleware/) |
| RBAC matrix | [`config/rbac/role-permission-matrix.yaml`](config/rbac/role-permission-matrix.yaml) |

### Install & test

```bash
pip install -e "libs/auth-middleware[dev]"
pip install -e "services/integration-api[dev]"
pytest libs/auth-middleware/tests services/integration-api/tests -q
```

### Integration sketch

```python
from asiwdp_auth import AuthMiddleware, ApiVersionMiddleware, AuthConfig

app.add_middleware(AuthMiddleware, config=AuthConfig.from_env(), rbac_matrix_path=...)
app.add_middleware(ApiVersionMiddleware, supported_versions=("v1", "v2"))
```

## OAuth2 / JWT Authentication Middleware

Reusable **`asiwdp-auth`** middleware library and supporting RBAC / OpenAPI
artifacts.

| Artifact | Path |
|----------|------|
| JWT claim schema & RBAC design | [`docs/design/jwt-claim-schema-and-rbac.md`](docs/design/jwt-claim-schema-and-rbac.md) |
| Role → permission matrix | [`config/rbac/role-permission-matrix.yaml`](config/rbac/role-permission-matrix.yaml) |
| Middleware package | [`libs/auth-middleware/`](libs/auth-middleware/) |
| Service OpenAPI specs | [`openapi/`](openapi/) |
