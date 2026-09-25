# Tenant Entity Schema and Default Configuration Model

**Story:** Build Automated Tenant Provisioning and Configuration Service  
**Story ID:** `486d3e38-2cec-40cb-874d-576d2147732c`  
**Task:** Design tenant entity schema and default config model (`89d8dbba-19a6-4a35-8382-d1be49c1fcf0`)

## 1. Overview

This document specifies the relational tables for PostgreSQL and collection schemas for MongoDB that support multi-tenant provisioning. The design ensures:

- `tenant_id` as the primary partition key for data isolation
- Idempotent provisioning via `idempotency_key` tracking
- Default configuration initialization at tenant creation
- Audit trail for compliance (GDPR/CCPA)

## 2. Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TENANT PROVISIONING SCHEMA                         │
└─────────────────────────────────────────────────────────────────────────────┘

┌───────────────────────┐       ┌───────────────────────────┐
│       TENANTS         │       │   TENANT_CONFIGURATIONS   │
├───────────────────────┤       ├───────────────────────────┤
│ PK tenant_id (UUID)   │──────<│ PK config_id (UUID)       │
│    name               │   1:N │ FK tenant_id (UUID)       │
│    slug               │       │    config_key             │
│    display_name       │       │    config_value (JSONB)   │
│    status             │       │    is_default             │
│    tier               │       │    created_at             │
│    owner_user_id      │       │    updated_at             │
│    contact_email      │       └───────────────────────────┘
│    metadata (JSONB)   │
│    created_at         │       ┌───────────────────────────┐
│    updated_at         │       │   TENANT_METADATA         │
│    provisioned_at     │       ├───────────────────────────┤
│    provisioned_by     │──────<│ PK metadata_id (UUID)     │
└───────────────────────┘   1:N │ FK tenant_id (UUID)       │
                                │    key                    │
                                │    value (JSONB)          │
                                │    scope                  │
                                │    created_at             │
                                │    updated_at             │
                                └───────────────────────────┘

┌───────────────────────┐       ┌───────────────────────────┐
│   IDEMPOTENCY_KEYS    │       │ TENANT_PROVISIONING_EVENTS│
├───────────────────────┤       ├───────────────────────────┤
│ PK idempotency_key    │       │ PK event_id (UUID)        │
│    tenant_id (UUID)   │       │ FK tenant_id (UUID)       │
│    request_hash       │       │    event_type             │
│    response (JSONB)   │       │    payload (JSONB)        │
│    created_at         │       │    emitted_at             │
│    expires_at         │       │    status                 │
└───────────────────────┘       └───────────────────────────┘
```

## 3. Table Descriptions

### 3.1 `tenants`
Core tenant entity storing identity and status information.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `tenant_id` | UUID | PK, NOT NULL | Unique tenant identifier (partition key) |
| `name` | VARCHAR(255) | NOT NULL, UNIQUE | Tenant name for display |
| `slug` | VARCHAR(100) | NOT NULL, UNIQUE | URL-safe identifier |
| `display_name` | VARCHAR(255) | | Optional friendly name |
| `status` | VARCHAR(50) | NOT NULL, DEFAULT 'provisioning' | Lifecycle status |
| `tier` | VARCHAR(50) | NOT NULL, DEFAULT 'standard' | Subscription tier |
| `owner_user_id` | UUID | | Initial admin user |
| `contact_email` | VARCHAR(255) | NOT NULL | Primary contact |
| `metadata` | JSONB | DEFAULT '{}' | Extensible attributes |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last update |
| `provisioned_at` | TIMESTAMPTZ | | When provisioning completed |
| `provisioned_by` | UUID | | User who initiated provisioning |

**Status Values:** `provisioning`, `active`, `suspended`, `deprovisioning`, `deleted`  
**Tier Values:** `free`, `standard`, `professional`, `enterprise`

### 3.2 `tenant_configurations`
Tenant-scoped configuration settings with defaults.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `config_id` | UUID | PK, NOT NULL | Configuration entry ID |
| `tenant_id` | UUID | FK, NOT NULL | References tenants |
| `config_key` | VARCHAR(255) | NOT NULL | Configuration key |
| `config_value` | JSONB | NOT NULL | Configuration value |
| `is_default` | BOOLEAN | DEFAULT true | Whether using default value |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last update |

**Unique Constraint:** `(tenant_id, config_key)`

### 3.3 `tenant_metadata`
Extensible key-value metadata scoped to tenants.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `metadata_id` | UUID | PK, NOT NULL | Metadata entry ID |
| `tenant_id` | UUID | FK, NOT NULL | References tenants |
| `key` | VARCHAR(255) | NOT NULL | Metadata key |
| `value` | JSONB | NOT NULL | Metadata value |
| `scope` | VARCHAR(100) | DEFAULT 'general' | Metadata scope/category |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last update |

**Unique Constraint:** `(tenant_id, key, scope)`

### 3.4 `idempotency_keys`
Tracks idempotency keys for replay protection.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `idempotency_key` | VARCHAR(255) | PK, NOT NULL | Client-provided key |
| `tenant_id` | UUID | | Created tenant ID |
| `request_hash` | VARCHAR(64) | NOT NULL | SHA-256 of request body |
| `response` | JSONB | NOT NULL | Cached response |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Creation timestamp |
| `expires_at` | TIMESTAMPTZ | NOT NULL | TTL for cleanup |

### 3.5 `tenant_provisioning_events`
Audit log for provisioning events (telemetry integration).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `event_id` | UUID | PK, NOT NULL | Event identifier |
| `tenant_id` | UUID | FK, NOT NULL | References tenants |
| `event_type` | VARCHAR(100) | NOT NULL | Event type |
| `payload` | JSONB | NOT NULL | Event details |
| `emitted_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Emission timestamp |
| `status` | VARCHAR(50) | DEFAULT 'pending' | Delivery status |

## 4. Default Configuration Template

When a tenant is provisioned, the following default configurations are initialized:

```json
{
  "features": {
    "skills_intelligence": true,
    "learning_paths": true,
    "recommendations": true,
    "analytics": true,
    "consent_management": true
  },
  "limits": {
    "max_users": 100,
    "max_organizations": 10,
    "max_skills": 5000,
    "max_learning_paths": 500,
    "storage_gb": 50
  },
  "privacy": {
    "data_retention_days": 365,
    "gdpr_enabled": true,
    "ccpa_enabled": true,
    "consent_required": true
  },
  "integrations": {
    "sso_enabled": false,
    "scim_enabled": false,
    "webhook_enabled": false
  },
  "branding": {
    "custom_logo_enabled": false,
    "custom_domain_enabled": false
  }
}
```

## 5. Indexing Strategy

| Table | Index | Columns | Type |
|-------|-------|---------|------|
| tenants | idx_tenants_slug | slug | UNIQUE |
| tenants | idx_tenants_status | status | B-tree |
| tenants | idx_tenants_tier | tier | B-tree |
| tenant_configurations | idx_tenant_configs_tenant | tenant_id | B-tree |
| tenant_configurations | idx_tenant_configs_key | tenant_id, config_key | UNIQUE |
| tenant_metadata | idx_tenant_metadata_tenant | tenant_id | B-tree |
| tenant_metadata | idx_tenant_metadata_key | tenant_id, key, scope | UNIQUE |
| idempotency_keys | idx_idempotency_expires | expires_at | B-tree |
| tenant_provisioning_events | idx_prov_events_tenant | tenant_id | B-tree |
| tenant_provisioning_events | idx_prov_events_emitted | emitted_at | B-tree |
