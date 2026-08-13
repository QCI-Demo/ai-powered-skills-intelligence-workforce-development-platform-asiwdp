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

### Install & test

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
