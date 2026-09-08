# AI-Powered Skills Intelligence & Workforce Development Platform (ASIWDP)

Multi-tenant SaaS platform foundation for skills intelligence, personalized
learning, and workforce readiness.

## Packages

| Artifact | Path |
|----------|------|
| JWT claim schema & RBAC design | [`docs/design/jwt-claim-schema-and-rbac.md`](docs/design/jwt-claim-schema-and-rbac.md) |
| Consent-aware ingestion design | [`docs/design/consent-aware-personal-data-ingestion.md`](docs/design/consent-aware-personal-data-ingestion.md) |
| Role → permission matrix | [`config/rbac/role-permission-matrix.yaml`](config/rbac/role-permission-matrix.yaml) |
| Auth middleware (`asiwdp-auth`) | [`libs/auth-middleware/`](libs/auth-middleware/) |
| Personal data + consent (`asiwdp-personal-data`) | [`libs/personal-data/`](libs/personal-data/) |
| Service OpenAPI specs | [`openapi/`](openapi/) |

## OAuth2 / JWT Authentication Middleware

Reusable **`asiwdp-auth`** middleware for tenant-scoped JWT authn/authz.

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

## Consent-Aware Personal Data Ingestion

Personal skill data writes query **`ConsentService`** before persistence and
return **HTTP 422** when a valid consent record is missing.

```bash
pip install -e "libs/personal-data[dev]"
pytest libs/personal-data/tests -q
```

```python
from asiwdp_personal_data import (
    ConsentService,
    InMemoryConsentStore,
    PersonalSkillDataIngestionPipeline,
    InMemoryPersonalSkillStore,
    ConsentMissingError,
)

consent = ConsentService(InMemoryConsentStore())
pipeline = PersonalSkillDataIngestionPipeline(
    consent_service=consent,
    skill_store=InMemoryPersonalSkillStore(),
)
# pipeline.ingest(...) → ConsentMissingError (status_code=422) if no grant
```
