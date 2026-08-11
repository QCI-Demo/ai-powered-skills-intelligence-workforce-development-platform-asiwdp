# asiwdp-auth

Reusable OAuth2/JWT authentication middleware with tenant-scoped RBAC for
ASIWDP micro-services.

## Install

```bash
pip install -e "libs/auth-middleware[dev]"
```

## Quick start (Starlette / FastAPI)

```python
from asiwdp_auth import AuthMiddleware, AuthConfig, require_permission

app.add_middleware(
    AuthMiddleware,
    config=AuthConfig.from_env(),
    rbac_matrix_path="config/rbac/role-permission-matrix.yaml",
)

@app.get("/skills")
@require_permission("skills:read")
async def list_skills(request):
    principal = request.state.principal
    ...
```

## Features

- Validates Bearer JWTs (signature, issuer, audience, expiry)
- Extracts `tenant_id`, `roles`, `scopes` (camelCase aliases supported)
- Expands roles via the shared RBAC YAML matrix
- Aborts with 401 / 403 on authn / authz failure
- Never logs raw tokens

See `docs/design/jwt-claim-schema-and-rbac.md` for the claim schema.
