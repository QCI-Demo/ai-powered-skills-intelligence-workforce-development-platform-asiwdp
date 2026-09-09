# ASIWDP Skills API — Postman Collection

Automated functional tests for the Skills Framework service (CRUD, bulk
import/export, versioning, tenant isolation, malformed payloads).

## Files

| Path | Purpose |
|------|---------|
| `skills-api-collection.json` | Postman Collection v2.1 |
| `skills-api.environment.json` | Local environment (`tenant_id`, `version`, …) |
| `fixtures/` | Import payloads (valid + malformed JSON/CSV) |
| `scripts/generate_collection.py` | Regenerates the collection JSON |

## Variables

| Variable | Used for |
|----------|----------|
| `baseUrl` | API root (default `http://localhost:8080/api/v1`) |
| `tenant_id` | Tenant scope (substituted in bodies, headers, export query) |
| `version` | Current taxonomy revision (`X-Taxonomy-Version` + query/body) |
| `historic_version` | Historic snapshot for versioning scenarios |
| `access_token` | OAuth2 Bearer JWT (do **not** commit real tokens) |
| `skill_id` / `category_id` / `proficiency_id` | Chained CRUD IDs |

## Folders

1. **Health** — `GET /health`
2. **Skills CRUD (valid)** — create / list / get / patch / search / retire
3. **Skills CRUD (malformed)** — 400/401/404 validation cases
4. **Categories CRUD** — valid + malformed
5. **Proficiencies CRUD** — valid + malformed
6. **Bulk Import** — `/taxonomy/import` JSON/CSV success + row-level errors
7. **Bulk Export** — `/taxonomy/export` JSON/CSV, historic version, tenant mismatch
8. **Versioning** — header/query isolation across taxonomy revisions
9. **Tenant Isolation** — JWT tenant wins over body `tenant_id`

Each request includes Postman test scripts that assert **status codes** and
**response schema** (Skill, PaginatedSkills, ImportReport, TaxonomyExport, Error).
Happy-path reads also check the **under-50ms** SLA from the epic.

## Run with Newman (CI)

```bash
# Install once
npm install -g newman newman-reporter-htmlextra

# Provide a short-lived token via env (never hardcode secrets)
export POSTMAN_ACCESS_TOKEN="…"

newman run tests/postman/skills-api-collection.json \
  -e tests/postman/skills-api.environment.json \
  --env-var "access_token=${POSTMAN_ACCESS_TOKEN}" \
  --working-dir tests/postman \
  -r cli,htmlextra \
  --reporter-htmlextra-export reports/skills-api-newman.html
```

`--working-dir tests/postman` is required so multipart `fixtures/…` paths resolve.

## Regenerate

```bash
python3 tests/postman/scripts/generate_collection.py
```

## Security notes

- Collection/environment ship with empty `access_token`.
- Synthetic UUIDs only — no customer or employee PII.
- Do not commit real JWTs, client secrets, or production tenant IDs.
