# asiwdp-ingestion

JSON Schema validation for ASIWDP workforce and learning-data ingestion
pipelines. Loads contracts from `contracts/ingestion/`, validates payloads with
`jsonschema` (Draft 2020-12), and maps failures to a **tenant-scoped HTTP 422**
error model with field details.

## Install

```bash
pip install -e "libs/ingestion-validation[dev]"
# optional Starlette helpers:
pip install -e "libs/ingestion-validation[dev,starlette]"
```

## Quick start

```python
from asiwdp_ingestion import IngestionValidator

validator = IngestionValidator.from_contracts_root("contracts/ingestion")

result = validator.validate(
    "employee",
    payload,
    tenant_id=principal.tenant_id,
    correlation_id=request.headers.get("X-Correlation-Id"),
)

if not result.ok:
    status, body = result.to_http_response()  # 422
    # body["details"] → [{ field, code, message, schemaPath? }, ...]
```

Or raise:

```python
from asiwdp_ingestion.error_mapper import ValidationFailed

try:
    clean = validator.validate_or_raise("role", payload, tenant_id=tenant_id)
except ValidationFailed as exc:
    status, body = exc.error.status, exc.to_dict()
```

## Contracts

| Contract ID | Schema |
|-------------|--------|
| `employee` | `contracts/ingestion/v1/employee.schema.json` |
| `role` | `contracts/ingestion/v1/role.schema.json` |
| `learning-content` | `contracts/ingestion/v1/learning-content.schema.json` |
| `learner-activity` | `contracts/ingestion/v1/learner-activity.schema.json` |

Override the contracts root with `ASIWDP_INGESTION_CONTRACTS_PATH` or
`IngestionValidator.from_contracts_root(path)`.

## Error model (HTTP 422)

```json
{
  "error": "validation_failed",
  "message": "Payload failed contract validation (2 field errors)",
  "status": 422,
  "tenantId": "11111111-1111-1111-1111-111111111111",
  "contract": "employee",
  "schemaVersion": "1.0.0",
  "correlationId": "req-abc",
  "details": [
    {
      "field": "/employee/workEmail",
      "code": "format",
      "message": "'not-an-email' is not a 'email'",
      "schemaPath": "/properties/employee/properties/workEmail/format"
    }
  ]
}
```

Rejected instance values are **not** included in responses (PII-safe).

Tenant mismatch (`payload.tenantId` ≠ JWT tenant) raises `TenantMismatchError`
(HTTP 403), not 422.

## Tests

```bash
pip install -e "libs/ingestion-validation[dev]"
pytest libs/ingestion-validation/tests -q
```
