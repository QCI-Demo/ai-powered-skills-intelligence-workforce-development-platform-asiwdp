# AI-Powered Skills Intelligence & Workforce Development Platform (ASIWDP)

Multi-tenant SaaS platform foundation for skills intelligence, personalized
learning, and workforce readiness.

## OAuth2 / JWT Authentication Middleware

This repository delivers the reusable **`asiwdp-auth`** middleware library and
supporting RBAC / OpenAPI artifacts for story
`6db721b1-7e99-4f99-992e-2bfda2e66a84`.

| Artifact | Path |
|----------|------|
| JWT claim schema & RBAC design | [`docs/design/jwt-claim-schema-and-rbac.md`](docs/design/jwt-claim-schema-and-rbac.md) |
| Role → permission matrix | [`config/rbac/role-permission-matrix.yaml`](config/rbac/role-permission-matrix.yaml) |
| Middleware package | [`libs/auth-middleware/`](libs/auth-middleware/) |
| Service OpenAPI specs | [`openapi/`](openapi/) |
| API portal staging | [`openapi/portal/`](openapi/portal/) |

## Skills Framework OpenAPI

Versioned CRUD, bulk import/export, taxonomy version header, and tenant
security scopes live in
[`openapi/skills-framework-service.yaml`](openapi/skills-framework-service.yaml).

```bash
pip install "openapi-spec-validator>=0.7.0" PyYAML
./scripts/validate_and_publish_openapi.sh
```

### Install & test (auth middleware)

```bash
pip install -e "libs/auth-middleware[dev]"
pytest libs/auth-middleware/tests -q
```

### Integration sketch

```python
from asiwdp_auth import AuthMiddleware, AuthConfig

app.add_middleware(
    AuthMiddleware,
    config=AuthConfig.from_env(),
    rbac_matrix_path="config/rbac/role-permission-matrix.yaml",
)
```
