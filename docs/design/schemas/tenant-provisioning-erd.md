# Tenant Provisioning Entity-Relationship Diagram

## Overview

This document describes the data model for the tenant provisioning service, supporting
both PostgreSQL (relational) and MongoDB (document store) implementations.

## Entity Relationships

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            TENANT PROVISIONING SCHEMA                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌───────────────────────┐         ┌───────────────────────────┐               │
│  │       TENANT          │         │   TENANT_CONFIGURATION    │               │
│  ├───────────────────────┤         ├───────────────────────────┤               │
│  │ PK tenant_id (UUID)   │────────►│ PK config_id (UUID)       │               │
│  │    name               │    1:N  │ FK tenant_id (UUID)       │               │
│  │    display_name       │         │    config_key             │               │
│  │    domain             │         │    config_value (JSONB)   │               │
│  │    status             │         │    category               │               │
│  │    plan_tier          │         │    is_active              │               │
│  │    settings (JSONB)   │         │    version                │               │
│  │    created_at         │         │    created_at             │               │
│  │    updated_at         │         │    updated_at             │               │
│  │    created_by         │         │                           │               │
│  │    provisioned_at     │         │ UNIQUE(tenant_id,         │               │
│  │    deprovisioned_at   │         │        config_key)        │               │
│  └───────────────────────┘         └───────────────────────────┘               │
│            │                                                                    │
│            │ 1:N                                                                │
│            ▼                                                                    │
│  ┌───────────────────────┐         ┌───────────────────────────┐               │
│  │   TENANT_METADATA     │         │    IDEMPOTENCY_KEY        │               │
│  ├───────────────────────┤         ├───────────────────────────┤               │
│  │ PK metadata_id (UUID) │         │ PK idempotency_key        │               │
│  │ FK tenant_id (UUID)   │         │    tenant_id (UUID)       │               │
│  │    metadata_key       │         │    request_hash           │               │
│  │    metadata_value     │         │    response_body (JSONB)  │               │
│  │    created_at         │         │    status_code            │               │
│  │    updated_at         │         │    created_at             │               │
│  │                       │         │    expires_at             │               │
│  │ UNIQUE(tenant_id,     │         │                           │               │
│  │        metadata_key)  │         │ INDEX ON expires_at       │               │
│  └───────────────────────┘         └───────────────────────────┘               │
│            │                                                                    │
│            │                                                                    │
│            ▼                                                                    │
│  ┌───────────────────────┐         ┌───────────────────────────┐               │
│  │ PROVISIONING_EVENT    │         │   TENANT_AUDIT_LOG        │               │
│  ├───────────────────────┤         ├───────────────────────────┤               │
│  │ PK event_id (UUID)    │         │ PK audit_id (UUID)        │               │
│  │ FK tenant_id (UUID)   │         │ FK tenant_id (UUID)       │               │
│  │    event_type         │         │    action                 │               │
│  │    event_payload      │         │    actor_id               │               │
│  │    status             │         │    actor_type             │               │
│  │    published_at       │         │    resource_type          │               │
│  │    created_at         │         │    resource_id            │               │
│  │                       │         │    changes (JSONB)        │               │
│  │ INDEX ON (tenant_id,  │         │    created_at             │               │
│  │           event_type) │         │                           │               │
│  └───────────────────────┘         │ INDEX ON (tenant_id,      │               │
│                                    │           created_at)     │               │
│                                    └───────────────────────────┘               │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Tenant Status Lifecycle

```
    ┌──────────────────────────────────────────────────────────────┐
    │                                                              │
    │    ┌──────────┐    provision    ┌──────────┐                 │
    │    │ PENDING  │───────────────►│  ACTIVE  │                 │
    │    └──────────┘                 └──────────┘                 │
    │         │                            │                       │
    │         │ failure                    │ suspend               │
    │         ▼                            ▼                       │
    │    ┌──────────┐                ┌───────────┐                 │
    │    │  FAILED  │                │ SUSPENDED │                 │
    │    └──────────┘                └───────────┘                 │
    │         │                            │                       │
    │         │ retry                      │ reactivate            │
    │         └─────────►┌─────────┐◄──────┘                       │
    │                    │ PENDING │                               │
    │                    └─────────┘                               │
    │                         │                                    │
    │                         │ deprovision                        │
    │                         ▼                                    │
    │                    ┌───────────────┐                         │
    │                    │ DEPROVISIONED │                         │
    │                    └───────────────┘                         │
    │                                                              │
    └──────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

1. **tenant_id as Partition Key**: All tenant-scoped tables use `tenant_id` as the
   primary reference for data isolation and partitioning.

2. **JSONB for Flexible Data**: Settings, configuration values, and event payloads
   use JSONB to accommodate evolving schemas without migrations.

3. **Idempotency Store**: Separate table for idempotency keys with TTL support
   to enable safe retry of provisioning requests.

4. **Audit Trail**: Complete audit logging for compliance with GDPR/CCPA requirements.

5. **Event Sourcing Ready**: Provisioning events stored for downstream processing
   and eventual consistency patterns.
