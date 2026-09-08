# Consent-Aware Personal Skill Data Ingestion

**Story:** Implement Consent-Aware Personal Data Service and Usage-Metering Collector  
**Task:** Integrate consent checks into data ingestion pipelines  
**Aligned with:** GDPR / CCPA personal-data handling for ASIWDP

## 1. Purpose

Personal skill profiles, proficiency assessments, and related learner attributes
are personal data. Before any mutating ingestion path persists such records,
the pipeline must verify that a valid consent record exists for the subject
within the caller's tenant boundary.

## 2. Consent record (canonical fields)

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Consent record identifier |
| `tenant_id` | UUID | Tenant isolation boundary |
| `subject_id` | UUID | Data subject (learner / employee) |
| `purpose` | string | Processing purpose key |
| `status` | enum | `granted` \| `revoked` \| `expired` |
| `granted_at` | datetime (UTC) | When consent was given |
| `expires_at` | datetime (UTC), optional | Soft expiry; treated as invalid after this instant |
| `revoked_at` | datetime (UTC), optional | When consent was withdrawn |
| `policy_version` | string | Privacy / notice version acknowledged |
| `source` | string | Capture channel (`api`, `ui`, `import`, …) |

### Purpose used by personal skill ingestion

`personal_skill_data_processing`

## 3. Ingestion pre-processing

Every personal-skill ingest path runs this guard **before** persistence:

1. Resolve `(tenant_id, subject_id, purpose)`.
2. Query `ConsentService.has_valid_consent(...)`.
3. If no valid grant → abort with **HTTP 422 Unprocessable Entity**.
4. Otherwise persist the personal skill payload.

Fail-closed: missing, revoked, or expired consent is treated as absent.

## 4. HTTP 422 contract

```json
{
  "error": "consent_missing",
  "message": "Valid consent required before persisting personal skill data",
  "purpose": "personal_skill_data_processing",
  "subject_id": "<uuid>",
  "tenant_id": "<uuid>"
}
```

| Status | When |
|--------|------|
| 401 / 403 | Authn / authz failures (handled by `asiwdp-auth`) |
| **422** | Request authenticated but consent missing / invalid |
| 201 | Ingested after consent verification |

## 5. Library artifact

Reusable package: [`libs/personal-data/`](../../libs/personal-data/)
(`asiwdp-personal-data`). Unit tests cover the consent guard in isolation from
transport and storage backends.
