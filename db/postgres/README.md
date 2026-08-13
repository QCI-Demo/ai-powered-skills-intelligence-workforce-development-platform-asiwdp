# PostgreSQL Skills Taxonomy Schema

Flyway (primary) and Liquibase (alternate) migrations for the ASIWDP skills
taxonomy.

## Migrations

| Version | File | Purpose |
|---------|------|---------|
| V1 | `sql/V1__create_skill_taxonomy_schema.sql` | Create tables + indexes |
| U1 | `undo/U1__drop_skill_taxonomy_schema.sql` | Drop schema (down) |
| V2 | `sql/V2__seed_demo_tenant_taxonomy.sql` | Idempotent demo-tenant seed |
| U2 | `undo/U2__unseed_demo_tenant_taxonomy.sql` | Remove demo seed (down) |
| V3 | `sql/V3__add_category_and_retire_support.sql` | Category table + retire/audit |
| U3 | `undo/U3__drop_category_and_retire_support.sql` | Drop category / retire (down) |
| R | `sql/R__seed_tenant_taxonomy_procedure.sql` | Repeatable seed helper function |

## Migrate

```bash
flyway -configFiles=config/flyway/flyway.conf \
  -url=jdbc:postgresql://localhost:5432/asiwdp_skills \
  -user="$ASIWDP_DB_USER" -password="$ASIWDP_DB_PASSWORD" \
  -locations=filesystem:db/postgres/sql \
  migrate
```

## Test on a clean database

```bash
./scripts/test_postgres_migration.sh
```

## Seed a new tenant

```sql
SELECT asiwdp_seed_tenant_taxonomy('xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx', 1);
```

## Liquibase

See `liquibase/changelog-master.xml` for an equivalent changelog with rollback
blocks wrapping the same SQL files.
