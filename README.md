# AI-Powered Skills Intelligence & Workforce Development Platform (ASIWDP)

Multi-tenant SaaS platform foundation for skills intelligence, personalized
learning, and workforce readiness.

## Libraries

| Artifact | Path |
|----------|------|
| JWT claim schema & RBAC design | [`docs/design/jwt-claim-schema-and-rbac.md`](docs/design/jwt-claim-schema-and-rbac.md) |
| Role → permission matrix | [`config/rbac/role-permission-matrix.yaml`](config/rbac/role-permission-matrix.yaml) |
| Auth middleware (`asiwdp-auth`) | [`libs/auth-middleware/`](libs/auth-middleware/) |
| Ingestion contracts (JSON Schema) | [`contracts/ingestion/`](contracts/ingestion/) |
| Ingestion validation (`asiwdp-ingestion`) | [`libs/ingestion-validation/`](libs/ingestion-validation/) |
| Ingestion validation design | [`docs/design/ingestion-validation-layer.md`](docs/design/ingestion-validation-layer.md) |
| Service OpenAPI specs | [`openapi/`](openapi/) |

### Auth middleware — install & test

```bash
pip install -e "libs/auth-middleware[dev]"
pytest libs/auth-middleware/tests -q
```

```python
from asiwdp_auth import AuthMiddleware, AuthConfig

app.add_middleware(
    AuthMiddleware,
    config=AuthConfig.from_env(),
    rbac_matrix_path="config/rbac/role-permission-matrix.yaml",
)
```

### Ingestion validation — install & test

```bash
pip install -e "libs/ingestion-validation[dev]"
pytest libs/ingestion-validation/tests -q
```

```python
from asiwdp_ingestion import IngestionValidator

validator = IngestionValidator.from_contracts_root("contracts/ingestion")
result = validator.validate("employee", payload, tenant_id=tenant_id)
if not result.ok:
    status, body = result.to_http_response()  # HTTP 422 + field details
```
