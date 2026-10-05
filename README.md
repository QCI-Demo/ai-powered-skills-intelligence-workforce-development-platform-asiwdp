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
| Bias evaluator package | [`libs/bias-evaluator/`](libs/bias-evaluator/) |
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

## Model Bias & Fairness Evaluation

The **`asiwdp-bias-evaluator`** library provides automated fairness evaluation
for ML models, computing metrics like demographic parity and equal opportunity
across protected groups.

### Install & test

```bash
pip install -e "libs/bias-evaluator[dev]"
pytest libs/bias-evaluator/tests -q
```

### Usage

```python
from asiwdp_bias import BiasEvaluator, BiasConfig

config = BiasConfig.from_env()
evaluator = BiasEvaluator(config)

# Run bias evaluation
results = evaluator.evaluate_all_models(
    validation_data_path="data/validation.parquet",
    protected_attributes=["gender", "age_group", "ethnicity"]
)

# Check threshold (default ≤ 0.05)
for result in results:
    if result.threshold_breached:
        print(f"ALERT: Model {result.model_name} exceeds bias threshold!")
```

### CLI

```bash
# Evaluate all production models
bias-evaluator evaluate --validation-data data/validation.parquet

# CI/CD gate check
bias-evaluator check --model-name my-model --model-version 3 --validation-data data/validation.parquet
```
