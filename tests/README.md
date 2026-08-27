# ASIWDP Skills Service - Automated API Test Suites

This directory contains comprehensive automated tests for the Skills Framework Service, covering functional validation, tenant isolation, versioning, bulk import/export, and performance SLAs.

## Test Structure

```
tests/
├── postman/                    # Postman API test collections
│   ├── skills-api-collection.json
│   └── environment-template.json
├── integration/                # PyTest integration tests
│   ├── conftest.py
│   └── test_tenant_isolation.py
├── load/                       # k6 performance tests
│   └── skills-load-test.js
├── requirements.txt            # Python test dependencies
└── README.md                   # This file
```

## Quick Start

### 1. Postman Collection Tests

The Postman collection covers CRUD operations, bulk import/export, versioning, and authentication scenarios.

```bash
# Install Newman (Postman CLI)
npm install -g newman

# Run the collection
newman run postman/skills-api-collection.json \
  -e postman/environment-template.json \
  --env-var "API_BASE_URL=http://localhost:8080" \
  --env-var "TENANT_ID=your-tenant-id" \
  --env-var "ACCESS_TOKEN=your-jwt-token" \
  --reporters cli,junit \
  --reporter-junit-export results/postman-results.xml
```

### 2. Integration Tests (Tenant Isolation)

PyTest-based tests that validate tenant isolation and cross-tenant access restrictions.

```bash
# Install dependencies
pip install -r requirements.txt

# Run integration tests
pytest integration/ -v \
  --skills-api-url=http://localhost:8080/api/v1 \
  --tenant-a-token=$TENANT_A_TOKEN \
  --tenant-b-token=$TENANT_B_TOKEN \
  --html=results/integration-report.html

# Run with coverage
pytest integration/ --cov=. --cov-report=html
```

### 3. k6 Load Tests

Performance tests validating the <50ms (95th percentile) latency SLA.

```bash
# Install k6
# macOS: brew install k6
# Linux: https://k6.io/docs/getting-started/installation

# Run load test
k6 run load/skills-load-test.js \
  -e API_BASE_URL=http://localhost:8080 \
  -e TENANT_ID=your-tenant-id \
  -e TENANT_TOKEN=your-jwt-token

# Run with specific VUs and duration
k6 run load/skills-load-test.js --vus 100 --duration 5m

# Export results
k6 run load/skills-load-test.js --out json=results/k6-results.json
```

## CI Pipeline Integration

All test suites are designed for CI integration and produce JUnit XML reports.

### GitHub Actions Example

```yaml
name: Skills API Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Run Postman Tests
        uses: matt-ball/newman-action@master
        with:
          collection: tests/postman/skills-api-collection.json
          environment: tests/postman/environment-template.json
          reporters: junit
          reporter-junit-export: results/postman.xml
      
      - name: Run Integration Tests
        run: |
          pip install -r tests/requirements.txt
          pytest tests/integration/ --junitxml=results/integration.xml
      
      - name: Run Load Tests
        uses: grafana/k6-action@v0.3.0
        with:
          filename: tests/load/skills-load-test.js
          flags: --out json=results/k6.json
      
      - name: Upload Test Results
        uses: actions/upload-artifact@v4
        with:
          name: test-results
          path: results/
```

## Test Coverage

### Postman Collection (`skills-api-collection.json`)

| Category | Tests |
|----------|-------|
| Health Check | Liveness probe |
| Skills CRUD | Create, Read, Update, Delete |
| Bulk Operations | Import (valid/invalid), Export with filters |
| Versioning | Version history, specific version retrieval |
| Auth/Authz | Missing token, invalid token, insufficient permissions |
| Competencies | List, Create |

### Integration Tests (`test_tenant_isolation.py`)

| Test Class | Description |
|------------|-------------|
| TestTenantIsolation | Cross-tenant read/write/delete restrictions |
| TestAuditLogTenantIdentifiers | Audit logging with tenant context |
| TestTenantIsolationEdgeCases | Security edge cases (SQL injection, header mismatch) |

### Load Tests (`skills-load-test.js`)

| Metric | Threshold | Description |
|--------|-----------|-------------|
| http_req_duration{status:200} | p(95) < 50ms | Primary SLA |
| http_req_duration | avg < 30ms | Average latency |
| errors | rate < 1% | Error rate threshold |
| http_req_failed | rate < 5% | Request failure rate |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `API_BASE_URL` | Skills API base URL | http://localhost:8080 |
| `TENANT_ID` | Primary tenant ID | - |
| `TENANT_TOKEN` | OAuth2 token for primary tenant | - |
| `TENANT_A_ID` | Tenant A ID (isolation tests) | auto-generated |
| `TENANT_A_TOKEN` | Tenant A OAuth2 token | auto-generated |
| `TENANT_B_ID` | Tenant B ID (isolation tests) | auto-generated |
| `TENANT_B_TOKEN` | Tenant B OAuth2 token | auto-generated |
| `AUDIT_LOG_API_URL` | Audit service URL | http://localhost:8081/api/v1/audit |

## Test Reports

All test suites generate reports compatible with CI systems:

- **Postman/Newman**: JUnit XML via `--reporter-junit-export`
- **PyTest**: JUnit XML via `--junitxml`, HTML via `--html`
- **k6**: JUnit XML via the `jUnit()` handler in `handleSummary()`

Results are written to the `results/` directory.

## Related Documentation

- [Skills Framework OpenAPI Spec](../openapi/skills-framework-service.yaml)
- [RBAC Role-Permission Matrix](../config/rbac/role-permission-matrix.yaml)
- [JWT Claim Schema](../docs/design/jwt-claim-schema-and-rbac.md)
