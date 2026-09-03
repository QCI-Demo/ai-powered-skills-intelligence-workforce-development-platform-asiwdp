# PostgreSQL Skills Taxonomy Schema

Flyway (primary) and Liquibase (alternate) migrations for the ASIWDP skills
taxonomy. Scripts are idempotent and tenant-scoped.

## Migrations

| Version | File | Purpose |
|---------|------|---------|
| V1 (up) | `sql/V1__create_skill_taxonomy_schema.sql` | Create tables + indexes |
| U1 (down) | `undo/U1__drop_skill_taxonomy_schema.sql` | Drop schema |
| V2 (up) | `sql/V2__seed_demo_tenant_taxonomy.sql` | Idempotent demo-tenant seed |
| U2 (down) | `undo/U2__unseed_demo_tenant_taxonomy.sql` | Remove demo seed |
| R | `sql/R__seed_tenant_taxonomy_procedure.sql` | Repeatable seed helper function |

## Tables

- `skill` — hierarchical skill nodes (`tenant_id`, `version`, `code`)
- `proficiency` — ordered proficiency scale
- `role` — workforce / job roles (taxonomy, not IAM)
- `competency_requirement` — role → skill + required proficiency
- `audit_log` — append-only change history (`change_blob` JSONB)

All core tables carry `tenant_id` and `version` with composite unique keys and
`(tenant_id, version)` indexes for fast tenant-scoped reads.

## Migrate (up)

```bash
flyway -configFiles=config/flyway/flyway.conf \
  -url=jdbc:postgresql://localhost:5432/asiwdp_skills \
  -user="$ASIWDP_DB_USER" -password="$ASIWDP_DB_PASSWORD" \
  -locations=filesystem:db/postgres/sql \
  migrate
```

## Rollback (down)

```bash
psql -f db/postgres/undo/U2__unseed_demo_tenant_taxonomy.sql
psql -f db/postgres/undo/U1__drop_skill_taxonomy_schema.sql
```

Or via Liquibase rollback using `liquibase/changelog-master.xml`.

## Test on a clean database

```bash
./scripts/test_postgres_migration.sh
```

## Seed a new tenant

```sql
SELECT asiwdp_seed_tenant_taxonomy('xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx', 1);
```

Demo seed tenant id (dev only): `22222222-2222-2222-2222-222222222222`.
