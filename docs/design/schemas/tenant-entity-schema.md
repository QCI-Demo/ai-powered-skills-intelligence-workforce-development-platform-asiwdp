# Tenant Entity Schema Design

## Overview

This document describes the schema design for tenant provisioning, including entity relationships, PostgreSQL DDL, and MongoDB collection schemas.

## Entity Relationship Diagram

```mermaid
erDiagram
    TENANT ||--|| TENANT_CONFIGURATION : has
    TENANT ||--o{ TENANT_METADATA : contains
    TENANT ||--o{ IDEMPOTENCY_KEY : tracks
    
    TENANT {
        uuid id PK "Tenant unique identifier"
        string name "Display name"
        string slug UK "URL-safe unique slug"
        string status "active|suspended|provisioning"
        timestamp created_at "Creation timestamp"
        timestamp updated_at "Last update timestamp"
        string created_by "User who created tenant"
    }
    
    TENANT_CONFIGURATION {
        uuid id PK "Configuration ID"
        uuid tenant_id FK,UK "References TENANT"
        jsonb feature_flags "Feature toggles"
        jsonb limits "Usage limits"
        jsonb branding "Branding settings"
        jsonb integrations "Integration configs"
        int config_version "Optimistic lock version"
        timestamp created_at
        timestamp updated_at
    }
    
    TENANT_METADATA {
        uuid id PK "Metadata entry ID"
        uuid tenant_id FK "References TENANT"
        string key "Metadata key"
        string value "Metadata value"
        timestamp created_at
        timestamp updated_at
    }
    
    IDEMPOTENCY_KEY {
        uuid id PK "Key ID"
        string idempotency_key UK "Client-provided key"
        uuid tenant_id FK "Created tenant ID"
        jsonb request_hash "Request body hash"
        jsonb response "Stored response"
        timestamp created_at
        timestamp expires_at "TTL for cleanup"
    }
```

## PostgreSQL DDL

See `tenant-schema.sql` for complete DDL statements.

## MongoDB Collection Schema

See `tenant-schema-mongodb.json` for MongoDB validator schema.

## Partition Strategy

- **tenant_id** serves as the partition/shard key for all tenant-scoped tables
- All queries must include tenant_id to ensure proper routing
- Cross-tenant queries are restricted to platform_admin role only

## Indexing Strategy

### PostgreSQL
- Primary key indexes on all `id` columns
- Unique index on `tenants.slug`
- Unique index on `tenant_configurations.tenant_id`
- Composite index on `tenant_metadata(tenant_id, key)`
- Unique index on `idempotency_keys.idempotency_key`
- Partial index on `idempotency_keys.expires_at` for cleanup

### MongoDB
- Unique index on `_id` (tenant_id)
- Unique index on `slug`
- Index on `status` for filtering
- TTL index on idempotency collection for automatic expiration
