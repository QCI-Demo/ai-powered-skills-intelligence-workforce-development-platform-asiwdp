# Ingestion Payload Contracts

JSON Schema contracts for workforce and learning-data ingestion pipelines
(ASIWDP Integration APIs). Schemas are the source of truth for Story 001
ingestion validation and are loaded by `asiwdp-ingestion`.

## Layout

| Contract ID | Schema file | Domain |
|-------------|-------------|--------|
| `employee` | `v1/employee.schema.json` | HRIS employee master |
| `role` | `v1/role.schema.json` | Job / role definitions |
| `learning-content` | `v1/learning-content.schema.json` | LMS / content catalog |
| `learner-activity` | `v1/learner-activity.schema.json` | Learner progress events |

Shared definitions live in `v1/defs.schema.json` and are referenced via
`$ref` (`defs.schema.json#/$defs/...`).

## Versioning

- Directory `v1/` corresponds to schema major version `1`.
- Additive (backward-compatible) changes stay in `v1`.
- Breaking changes require a new major directory (`v2/`) and registry entry.

## Envelope fields (all payloads)

Every ingestion payload must include:

| Field | Type | Description |
|-------|------|-------------|
| `tenantId` | string (uuid) | Owning tenant (must match JWT `tenant_id`) |
| `sourceSystem` | string | Upstream system identifier (e.g. `workday`, `cornerstone`) |
| `sourceRecordId` | string | Stable id in the source system (dedupe key) |
| `idempotencyKey` | string | Caller-supplied idempotency key |
| `capturedAt` | string (date-time) | When the source captured the record |
| `consent` | object | Consent metadata (see defs) |

## Validation

Use the `asiwdp-ingestion` library:

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
    status, body = result.to_http_response()  # 422 + field details
```
