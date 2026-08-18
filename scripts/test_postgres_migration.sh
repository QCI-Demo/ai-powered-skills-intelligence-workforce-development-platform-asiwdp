#!/usr/bin/env bash
# Test Flyway migrations on a clean PostgreSQL database.
# Story task: 990ffe8b-8e74-40e5-8669-e385653fc17e
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FLYWAY_BIN="${FLYWAY_BIN:-$HOME/flyway/flyway}"
DB_NAME="${ASIWDP_TEST_DB:-asiwdp_skills_test}"
DB_USER="${ASIWDP_DB_USER:-asiwdp}"
DB_PASSWORD="${ASIWDP_DB_PASSWORD:-asiwdp_test}"
DB_HOST="${ASIWDP_DB_HOST:-localhost}"
DB_PORT="${ASIWDP_DB_PORT:-5432}"
JDBC_URL="jdbc:postgresql://${DB_HOST}:${DB_PORT}/${DB_NAME}"

if [[ ! -x "$FLYWAY_BIN" ]]; then
  echo "Flyway binary not found at $FLYWAY_BIN" >&2
  exit 1
fi

echo "==> Resetting clean test database: ${DB_NAME}"
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -v ON_ERROR_STOP=1 <<SQL
SELECT pg_terminate_backend(pid)
  FROM pg_stat_activity
 WHERE datname = '${DB_NAME}'
   AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS ${DB_NAME};
CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};
SQL

run_flyway() {
  local cmd="$1"
  shift || true
  "$FLYWAY_BIN" \
    -configFiles="$ROOT/config/flyway/flyway.conf" \
    -url="$JDBC_URL" \
    -user="$DB_USER" \
    -password="$DB_PASSWORD" \
    -locations="filesystem:$ROOT/db/postgres/sql" \
    "$cmd" "$@"
}

echo "==> Flyway migrate (up)"
run_flyway migrate

echo "==> Verifying schema + seed"
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 <<'SQL'
DO $$
DECLARE
  missing text;
BEGIN
  SELECT string_agg(t, ', ')
    INTO missing
    FROM unnest(ARRAY[
      'skill','proficiency','role','competency_requirement','audit_log'
    ]) AS t
   WHERE NOT EXISTS (
     SELECT 1 FROM information_schema.tables
      WHERE table_schema = 'public' AND table_name = t
   );
  IF missing IS NOT NULL THEN
    RAISE EXCEPTION 'Missing tables: %', missing;
  END IF;
END $$;

-- tenant_id + version columns present
SELECT table_name, column_name
  FROM information_schema.columns
 WHERE table_schema = 'public'
   AND column_name IN ('tenant_id', 'version')
   AND table_name IN (
     'skill','proficiency','role','competency_requirement','audit_log'
   )
 ORDER BY table_name, column_name;

-- required indexes
SELECT indexname
  FROM pg_indexes
 WHERE schemaname = 'public'
   AND indexname LIKE 'idx_%tenant%'
 ORDER BY indexname;

-- seed counts for demo tenant
SELECT 'skill' AS entity, COUNT(*) AS n FROM skill
 WHERE tenant_id = '22222222-2222-2222-2222-222222222222' AND version = 1
UNION ALL
SELECT 'proficiency', COUNT(*) FROM proficiency
 WHERE tenant_id = '22222222-2222-2222-2222-222222222222' AND version = 1
UNION ALL
SELECT 'role', COUNT(*) FROM role
 WHERE tenant_id = '22222222-2222-2222-2222-222222222222' AND version = 1
UNION ALL
SELECT 'competency_requirement', COUNT(*) FROM competency_requirement
 WHERE tenant_id = '22222222-2222-2222-2222-222222222222' AND version = 1
UNION ALL
SELECT 'audit_log', COUNT(*) FROM audit_log
 WHERE tenant_id = '22222222-2222-2222-2222-222222222222' AND version = 1;
SQL

echo "==> Re-run migrate (idempotent / no-op)"
run_flyway migrate

echo "==> Apply down scripts (U2 then U1) via psql"
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 \
  -f "$ROOT/db/postgres/undo/U2__unseed_demo_tenant_taxonomy.sql"
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 <<'SQL'
SELECT COUNT(*) AS remaining_seed_skills FROM skill
 WHERE tenant_id = '22222222-2222-2222-2222-222222222222';
SQL
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 \
  -f "$ROOT/db/postgres/undo/U1__drop_skill_taxonomy_schema.sql"

PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 <<'SQL'
SELECT COUNT(*) AS remaining_tables
  FROM information_schema.tables
 WHERE table_schema = 'public'
   AND table_name IN (
     'skill','proficiency','role','competency_requirement','audit_log'
   );
SQL

echo "==> Re-migrate after clean down (fresh up)"
# Clear flyway history since we manually applied undo SQL
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 <<'SQL'
DROP TABLE IF EXISTS flyway_schema_history;
SQL
run_flyway migrate

echo "==> Migration test suite passed"
