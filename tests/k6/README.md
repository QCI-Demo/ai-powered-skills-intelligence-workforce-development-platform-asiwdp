# ASIWDP Skills — k6 skill lookup load test

Concurrent `GET /skills` load test for the Skills Framework service.
Asserts the epic read SLA (**p95 under 50 ms** on successful responses) and
exports a **JUnit XML** report for CI.

## Files

| Path | Purpose |
|------|---------|
| `skill-lookup.js` | Load script (constant VUs → `GET /skills`) |
| `lib/junit.js` | Local JUnit XML formatter for `handleSummary` |

## Parameters

| Env var | Required | Default | Description |
|---------|----------|---------|-------------|
| `TENANT_TOKEN` | **yes** | — | OAuth2 Bearer JWT for the tenant under test |
| `QUERY` | no | _(empty)_ | Query string appended to `/skills` (without leading `?`) |
| `BASE_URL` | no | `http://localhost:8080/api/v1` | API root |
| `VUS` | no | `10` | Concurrent virtual users |
| `DURATION` | no | `30s` | Test duration |
| `JUNIT_OUT` | no | `k6-skill-lookup-junit.xml` | JUnit XML output path |

Examples for `QUERY`:

- `category=engineering&limit=50`
- `status=active&offset=0&limit=100`
- `version=1`

## Thresholds

```text
http_req_duration{status:200}  p(95) < 50
checks                         rate == 1
```

## Run locally

```bash
# Provide a short-lived tenant token (never commit real JWTs)
export TENANT_TOKEN="…"

k6 run \
  -e TENANT_TOKEN="$TENANT_TOKEN" \
  -e QUERY='category=engineering&limit=50' \
  -e VUS=20 \
  -e DURATION=1m \
  tests/k6/skill-lookup.js
```

JUnit report is written to `k6-skill-lookup-junit.xml` (override with `JUNIT_OUT`).

## CI usage

```bash
mkdir -p reports
k6 run \
  -e TENANT_TOKEN="$TENANT_TOKEN" \
  -e QUERY="$SKILLS_LOOKUP_QUERY" \
  -e BASE_URL="$SKILLS_BASE_URL" \
  -e JUNIT_OUT=reports/k6-skill-lookup-junit.xml \
  tests/k6/skill-lookup.js

# Publish reports/k6-skill-lookup-junit.xml as a CI test report artifact
```

k6 exits non-zero when thresholds fail, so the pipeline fails on SLA breach.

## Security notes

- Do **not** hardcode, log, or commit `TENANT_TOKEN` / production JWTs.
- Synthetic query params only — no customer or employee PII in scripts or fixtures.
