# AI-Powered Skills Intelligence & Workforce Development Platform (ASIWDP)

PostgreSQL migrations and tenant taxonomy seed scripts for the Skills Framework
& Competency Management Services.

## Quick start

```bash
# Apply Flyway migrations (schema + demo tenant seed)
flyway -configFiles=config/flyway/flyway.conf \
  -url=jdbc:postgresql://localhost:5432/asiwdp_skills \
  -user="$ASIWDP_DB_USER" -password="$ASIWDP_DB_PASSWORD" migrate

# Verify on a clean test database
./scripts/test_postgres_migration.sh
```

See [`db/postgres/README.md`](db/postgres/README.md) for up/down scripts,
Liquibase changelog, and tenant seed procedure usage.
