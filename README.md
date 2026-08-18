# AI-Powered Skills Intelligence & Workforce Development Platform (ASIWDP)

Multi-tenant SaaS platform foundation for skills intelligence, personalized
learning, and workforce readiness.

## ML models (recommendation, career forecast, adaptive sequencing)

Story `aa7842d6-de6d-4fa4-822f-b86245c6be73` delivers gradient-boosted /
tree-based model-serving components packaged with MLflow and versioned
`/predict` endpoints (rationale + model metadata on every response).

| Artifact | Path |
|----------|------|
| ML package | [`ml/`](ml/) |
| Design notes | [`docs/design/recommendation-forecast-sequencing-models.md`](docs/design/recommendation-forecast-sequencing-models.md) |
| CI (train / test / register / serve) | [`.github/workflows/ml-models.yml`](.github/workflows/ml-models.yml) |

```bash
pip install -e "ml[dev]"
pytest tests/ml -q
```

## OAuth2 / JWT Authentication Middleware

Reusable **`asiwdp-auth`** middleware library and supporting RBAC / OpenAPI
artifacts for story `6db721b1-7e99-4f99-992e-2bfda2e66a84`.

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
