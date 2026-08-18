# AI-Powered Skills Intelligence & Workforce Development Platform (ASIWDP)

Multi-tenant SaaS platform foundation for skills intelligence, personalized
learning, and workforce readiness.

## Persistent Domain Model (Skills Taxonomy)

Story `5ea02ecb-2f38-4d9b-a964-8cef5f85acac` delivers the tenant-scoped
PostgreSQL schema and MongoDB flexible-attribute collections for the skills
framework.

| Artifact | Path |
|----------|------|
| Design notes | [`docs/design/skill-taxonomy-persistent-model.md`](docs/design/skill-taxonomy-persistent-model.md) |
| PostgreSQL Flyway SQL | [`db/postgres/sql/`](db/postgres/sql/) |
| Liquibase changelog | [`db/postgres/liquibase/changelog-master.xml`](db/postgres/liquibase/changelog-master.xml) |
| MongoDB validators | [`db/mongodb/`](db/mongodb/) |
| Data-access layer | [`libs/skills-persistence/`](libs/skills-persistence/) |
| Migration test script | [`scripts/test_postgres_migration.sh`](scripts/test_postgres_migration.sh) |

### Migrate PostgreSQL

```bash
flyway -configFiles=config/flyway/flyway.conf \
  -url=jdbc:postgresql://localhost:5432/asiwdp_skills \
  -user="$ASIWDP_DB_USER" -password="$ASIWDP_DB_PASSWORD" \
  -locations=filesystem:db/postgres/sql \
  migrate
```

### Test migrations (clean DB)

```bash
./scripts/test_postgres_migration.sh
```

### MongoDB repositories

```bash
pip install -e "libs/skills-persistence[dev]"
pytest libs/skills-persistence/tests -q
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
