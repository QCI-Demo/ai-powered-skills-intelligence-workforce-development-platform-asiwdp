# asiwdp-auth

Reusable OAuth2/JWT authentication middleware with tenant-scoped RBAC for
ASIWDP micro-services.

## Install

```bash
pip install -e "libs/auth-middleware[dev]"
```

## Quick start (Starlette / FastAPI)

```python
from asiwdp_auth import (
    AuthMiddleware,
    ApiVersionMiddleware,
    AuthConfig,
    require_permission,
    require_scope,
)

app.add_middleware(
    AuthMiddleware,
    config=AuthConfig.from_env(),
    rbac_matrix_path="config/rbac/role-permission-matrix.yaml",
)
app.add_middleware(ApiVersionMiddleware, supported_versions=("v1", "v2"))

@app.get("/skills")
@require_permission("skills:read")
async def list_skills(request):
    principal = request.state.principal
    ...

@app.post("/api/v1/hris/employees")
@require_scope("hris:write")
async def ingest_employee(request):
    tenant = request.state.tenant_context
    ...
```

## Features

- Validates Bearer JWTs (signature, issuer, audience, expiry) via **PyJWT**
- Maps JWT claims to `tenant_id`, `roles`, `scopes` on `request.state.tenant_context`
- Expands roles via the shared RBAC YAML matrix
- Enforces scopes with `require_scope` / permissions with `require_permission`
- Stamps `X-API-Version` on every response (`ApiVersionMiddleware`)
- Aborts with 401 / 403 on authn / authz failure
- Never logs raw tokens

See `docs/design/jwt-claim-schema-and-rbac.md` and
`docs/design/api-versioning-and-scope-model.md`.
