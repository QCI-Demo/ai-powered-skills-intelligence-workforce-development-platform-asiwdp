# Tenant Entity Schema and Configuration Model

## Overview

This document defines the relational and document database schemas for tenant provisioning, ensuring `tenant_id` is the primary partition key for tenant isolation.

## ER Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TENANT PROVISIONING SCHEMA                         │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                                   tenants                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  PK  │ id                    UUID           NOT NULL                        │
│      │ name                  VARCHAR(255)   NOT NULL                        │
│      │ slug                  VARCHAR(100)   NOT NULL UNIQUE                 │
│      │ status                VARCHAR(50)    NOT NULL DEFAULT 'provisioning' │
│      │ tier                  VARCHAR(50)    NOT NULL DEFAULT 'standard'     │
│      │ contact_email         VARCHAR(320)   NOT NULL                        │
│      │ billing_email         VARCHAR(320)   NULL                            │
│      │ metadata              JSONB          NULL                            │
│      │ created_at            TIMESTAMPTZ    NOT NULL DEFAULT now()          │
│      │ updated_at            TIMESTAMPTZ    NOT NULL DEFAULT now()          │
│      │ provisioned_at        TIMESTAMPTZ    NULL                            │
│      │ deactivated_at        TIMESTAMPTZ    NULL                            │
│      │ created_by            UUID           NOT NULL                        │
└──────┴──────────────────────────────────────────────────────────────────────┘
         │
         │ 1
         │
         ▼ N
┌─────────────────────────────────────────────────────────────────────────────┐
│                            tenant_configurations                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  PK  │ id                    UUID           NOT NULL                        │
│  FK  │ tenant_id             UUID           NOT NULL REFERENCES tenants(id) │
│      │ config_key            VARCHAR(255)   NOT NULL                        │
│      │ config_value          JSONB          NOT NULL                        │
│      │ description           TEXT           NULL                            │
│      │ is_sensitive          BOOLEAN        NOT NULL DEFAULT false          │
│      │ created_at            TIMESTAMPTZ    NOT NULL DEFAULT now()          │
│      │ updated_at            TIMESTAMPTZ    NOT NULL DEFAULT now()          │
│      │ version               INTEGER        NOT NULL DEFAULT 1              │
│      │ UNIQUE(tenant_id, config_key)                                        │
└──────┴──────────────────────────────────────────────────────────────────────┘
         │
         │ 1
         │
         ▼ N
┌─────────────────────────────────────────────────────────────────────────────┐
│                             idempotency_keys                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  PK  │ id                    UUID           NOT NULL                        │
│  FK  │ tenant_id             UUID           NULL REFERENCES tenants(id)     │
│      │ idempotency_key       VARCHAR(255)   NOT NULL UNIQUE                 │
│      │ operation             VARCHAR(100)   NOT NULL                        │
│      │ resource_id           UUID           NULL                            │
│      │ request_hash          VARCHAR(64)    NOT NULL                        │
│      │ response_data         JSONB          NULL                            │
│      │ status                VARCHAR(50)    NOT NULL DEFAULT 'pending'      │
│      │ created_at            TIMESTAMPTZ    NOT NULL DEFAULT now()          │
│      │ expires_at            TIMESTAMPTZ    NOT NULL                        │
└──────┴──────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           tenant_audit_logs                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  PK  │ id                    UUID           NOT NULL                        │
│  FK  │ tenant_id             UUID           NOT NULL REFERENCES tenants(id) │
│      │ actor_id              UUID           NOT NULL                        │
│      │ actor_type            VARCHAR(50)    NOT NULL DEFAULT 'user'         │
│      │ action                VARCHAR(100)   NOT NULL                        │
│      │ resource_type         VARCHAR(100)   NOT NULL                        │
│      │ resource_id           UUID           NULL                            │
│      │ old_value             JSONB          NULL                            │
│      │ new_value             JSONB          NULL                            │
│      │ ip_address            INET           NULL                            │
│      │ user_agent            TEXT           NULL                            │
│      │ created_at            TIMESTAMPTZ    NOT NULL DEFAULT now()          │
└──────┴──────────────────────────────────────────────────────────────────────┘
```

## Tenant Status Lifecycle

```
  provisioning ──► active ──► suspended ──► deactivated
       │                           │
       │                           │
       └─────► failed              └──────► active (reactivation)
```

## Tenant Tiers

| Tier       | Description                          |
|------------|--------------------------------------|
| free       | Limited features, trial period       |
| standard   | Full features, standard support      |
| enterprise | Full features, priority support, SLA |

## Default Configuration Keys

| Key                              | Default Value               | Description                           |
|----------------------------------|-----------------------------|---------------------------------------|
| `features.skills_framework`      | `true`                      | Enable skills framework               |
| `features.recommendations`       | `true`                      | Enable AI recommendations             |
| `features.learning_paths`        | `true`                      | Enable learning paths                 |
| `features.analytics`             | `true`                      | Enable analytics dashboard            |
| `limits.max_users`               | `100` (standard)            | Maximum users allowed                 |
| `limits.max_organizations`       | `10` (standard)             | Maximum organizations                 |
| `limits.api_rate_limit`          | `1000` requests/min         | API rate limiting                     |
| `retention.audit_logs_days`      | `365`                       | Audit log retention                   |
| `retention.analytics_days`       | `730`                       | Analytics data retention              |
| `privacy.data_region`            | `"us-east-1"`               | Data residency region                 |
| `privacy.gdpr_enabled`           | `true`                      | GDPR compliance features              |
| `branding.logo_url`              | `null`                      | Custom logo URL                       |
| `branding.primary_color`         | `"#1a73e8"`                 | Primary brand color                   |
| `notifications.email_enabled`    | `true`                      | Email notifications                   |
| `notifications.webhook_url`      | `null`                      | Webhook for events                    |

## Indexes

- `tenants`: `idx_tenants_slug`, `idx_tenants_status`, `idx_tenants_created_at`
- `tenant_configurations`: `idx_tenant_configs_tenant_id`, `idx_tenant_configs_key`
- `idempotency_keys`: `idx_idempotency_expires_at` (for cleanup jobs)
- `tenant_audit_logs`: `idx_audit_tenant_created`, `idx_audit_action`
