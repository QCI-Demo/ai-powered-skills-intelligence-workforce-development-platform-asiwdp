# Ingestion Validation Layer

**Project:** ASIWDP  
**Story:** Build Validated Workforce and Learning-Data Ingestion Pipelines  
**Component:** Contract-driven JSON Schema validation + tenant-scoped 422 mapping

## 1. Purpose

Every secured integration API that accepts employee, role, learning-content, or
learner-activity payloads must:

1. Load the matching JSON Schema from `contracts/ingestion/`
2. Validate the incoming body with Draft 2020-12 (`jsonschema`)
3. Enforce tenant scope (`payload.tenantId` == authenticated `tenant_id`)
4. Return **HTTP 422** with field-level details on schema failure
5. Expose enough structure for processing-status endpoints to surface failures

## 2. Flow

```
Request (JWT + body)
        │
        ▼
┌───────────────────┐
│ Auth middleware   │  tenant_id from token
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ SchemaRegistry    │  load contracts/ingestion/v1/{contract}.schema.json
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐     mismatch
│ Tenant check      │──────────────► HTTP 403 tenant_mismatch
└─────────┬─────────┘
          │ match
          ▼
┌───────────────────┐
│ Draft202012       │  iter_errors(payload)
│ Validator         │
└─────────┬─────────┘
          │
     valid / invalid
          │
          ▼
┌───────────────────┐
│ error_mapper      │  FieldViolation[] → TenantScopedValidationError
└─────────┬─────────┘
          │
          ▼
   HTTP 422 JSON body   or   continue to dedupe / consent / route
```

## 3. Library

Package: `asiwdp-ingestion` (`libs/ingestion-validation/`)

| Module | Responsibility |
|--------|----------------|
| `schema_registry` | Discover & compile contract schemas |
| `validator` | Orchestrate tenant check + schema validation |
| `error_mapper` | Map `jsonschema` errors → 422 model |
| `models` | `FieldViolation`, `TenantScopedValidationError`, `ValidationResult` |
| `http` | Optional Starlette `JSONResponse` helpers |

## 4. Privacy

- Error details include **field path**, **keyword code**, and **message** only.
- Instance (rejected) values are never returned, avoiding PII in client-visible
  validation responses and default logs.
- Tenant mismatch responses do not echo the foreign `tenantId` from the body.

## 5. Processing status

Downstream ingestion workers should persist `TenantScopedValidationError.to_dict()`
(or equivalent) against the batch / idempotency key so tenants can query
validation and failure details via processing-status APIs.
