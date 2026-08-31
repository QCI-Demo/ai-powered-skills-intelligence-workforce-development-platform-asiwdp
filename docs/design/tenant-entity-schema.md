# Tenant Entity Schema & Default Configuration Model

**Story:** Build Automated Tenant Provisioning and Configuration Service  
**Story ID:** `486d3e38-2cec-40cb-874d-576d2147732c`  
**Task:** `89d8dbba-19a6-4a35-8382-d1be49c1fcf0`

Partition / isolation key for every tenant-owned row and document: **`tenant_id` (UUID)**.

## ER Diagram

```mermaid
erDiagram
    TENANT ||--o| TENANT_CONFIGURATION : has
    TENANT ||--o{ TENANT_METADATA : stores
    TENANT ||--o{ IDEMPOTENCY_RECORD : keyed_by
    TENANT {
        uuid tenant_id PK "partition key"
        string slug UK
        string display_name
        string status
        string plan_code
        string data_residency
        uuid created_by
        timestamptz created_at
        timestamptz updated_at
        timestamptz provisioned_at
    }
    TENANT_CONFIGURATION {
        uuid tenant_id PK_FK "partition key"
        jsonb defaults
        string locale
        string timezone
        boolean metering_enabled
        boolean gdpr_enabled
        boolean ccpa_enabled
        integer schema_version
        timestamptz created_at
        timestamptz updated_at
    }
    TENANT_METADATA {
        uuid id PK
        uuid tenant_id FK "partition key"
        string meta_key
        jsonb meta_value
        string created_by
        timestamptz created_at
        timestamptz updated_at
    }
    IDEMPOTENCY_RECORD {
        string idempotency_key PK
        uuid tenant_id FK "partition key"
        string request_hash
        integer response_status
        jsonb response_body
        timestamptz created_at
        timestamptz expires_at
    }
```

## Default configuration model

Applied atomically on successful `POST /api/tenants`:

| Field | Default | Notes |
| --- | --- | --- |
| `locale` | `en-US` | BCP-47 |
| `timezone` | `UTC` | IANA |
| `schema_version` | `1` | Config document version |
| `metering_enabled` | `true` | Usage capture on |
| `gdpr_enabled` | `true` | Consent-aware handling |
| `ccpa_enabled` | `true` | US privacy baseline |
| `defaults.features` | skills, learning_paths, analytics | Feature flags |
| `defaults.privacy.retention_days` | `365` | Soft retention hint |

Request may override locale, timezone, plan, residency, and metadata; feature/privacy defaults always seed unless explicitly overridden in `configuration`.

## Artifacts

| Store | Path |
| --- | --- |
| PostgreSQL DDL | `db/postgres/sql/V1__create_tenant_provisioning_schema.sql` |
| MongoDB validators | `db/mongodb/collections/*.validator.json` |
| MongoDB init | `db/mongodb/init/create_tenant_collections.js` |
