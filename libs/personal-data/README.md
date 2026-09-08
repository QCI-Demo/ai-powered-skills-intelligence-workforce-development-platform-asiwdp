# asiwdp-personal-data

Consent-aware personal skill data ingestion for ASIWDP. Data-ingestion
pipelines query `ConsentService` before persisting personal skill records and
reject requests with **HTTP 422** when a valid consent record is missing.

## Install

```bash
pip install -e "libs/personal-data[dev]"
```

## Consent guard (ingestion pre-processing)

```python
from asiwdp_personal_data import (
    ConsentService,
    InMemoryConsentStore,
    PersonalSkillDataIngestionPipeline,
    InMemoryPersonalSkillStore,
)

consent = ConsentService(InMemoryConsentStore())
pipeline = PersonalSkillDataIngestionPipeline(
    consent_service=consent,
    skill_store=InMemoryPersonalSkillStore(),
)

# Raises ConsentMissingError (HTTP 422) when no valid consent exists
record = pipeline.ingest(
    tenant_id=tenant_id,
    subject_id=subject_id,
    skill_code="PYTHON",
    proficiency_level=3,
)
```

## HTTP integration sketch

```python
from starlette.responses import JSONResponse
from asiwdp_personal_data import ConsentMissingError

try:
    record = pipeline.ingest(...)
except ConsentMissingError as exc:
    return JSONResponse(status_code=422, content=exc.to_error_body())
```

## Purpose key

Personal skill data uses purpose
`personal_skill_data_processing`. Consent must be `granted`, not revoked, and
not past `expires_at` for the `(tenant_id, subject_id, purpose)` tuple.

See `docs/design/consent-aware-personal-data-ingestion.md`.
