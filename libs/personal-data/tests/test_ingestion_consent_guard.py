"""Unit tests for the personal-skill ingestion consent guard."""

from __future__ import annotations

from uuid import UUID

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from asiwdp_personal_data import (
    PERSONAL_SKILL_DATA_PURPOSE,
    ConsentMissingError,
    ConsentService,
    InMemoryPersonalSkillStore,
    PersonalSkillDataIngestionPipeline,
)
from asiwdp_personal_data.http import consent_error_response
from asiwdp_personal_data.ingestion import ConsentGuard

TENANT = UUID("22222222-2222-2222-2222-222222222222")
SUBJECT = UUID("11111111-1111-1111-1111-111111111111")


class TestConsentGuard:
    """Isolated guard logic: queries ConsentService, raises 422 semantics."""

    def test_require_valid_consent_raises_when_missing(
        self, consent_service: ConsentService
    ) -> None:
        guard = ConsentGuard(consent_service)
        with pytest.raises(ConsentMissingError) as exc_info:
            guard.require_valid_consent(tenant_id=TENANT, subject_id=SUBJECT)

        err = exc_info.value
        assert err.status_code == 422
        assert err.error_code == "consent_missing"
        assert err.tenant_id == TENANT
        assert err.subject_id == SUBJECT
        assert err.purpose == PERSONAL_SKILL_DATA_PURPOSE
        body = err.to_error_body()
        assert body["error"] == "consent_missing"
        assert body["tenant_id"] == str(TENANT)
        assert body["subject_id"] == str(SUBJECT)
        assert body["purpose"] == PERSONAL_SKILL_DATA_PURPOSE

    def test_require_valid_consent_returns_consent_id_when_granted(
        self, consent_service: ConsentService
    ) -> None:
        granted = consent_service.grant(tenant_id=TENANT, subject_id=SUBJECT)
        guard = ConsentGuard(consent_service)
        consent_id = guard.require_valid_consent(
            tenant_id=TENANT, subject_id=SUBJECT
        )
        assert consent_id == granted.id

    def test_revoked_consent_fails_guard(
        self, consent_service: ConsentService
    ) -> None:
        consent_service.grant(tenant_id=TENANT, subject_id=SUBJECT)
        consent_service.revoke(tenant_id=TENANT, subject_id=SUBJECT)
        guard = ConsentGuard(consent_service)
        with pytest.raises(ConsentMissingError):
            guard.require_valid_consent(tenant_id=TENANT, subject_id=SUBJECT)


class TestIngestionPipelineConsentPreprocessing:
    """Pipeline must not persist personal skill data without consent."""

    def test_ingest_without_consent_raises_422_and_persists_nothing(
        self,
        pipeline: PersonalSkillDataIngestionPipeline,
        skill_store: InMemoryPersonalSkillStore,
    ) -> None:
        with pytest.raises(ConsentMissingError) as exc_info:
            pipeline.ingest(
                tenant_id=TENANT,
                subject_id=SUBJECT,
                skill_code="PYTHON",
                proficiency_level=3,
            )
        assert exc_info.value.status_code == 422
        assert skill_store.records == []

    def test_ingest_with_valid_consent_persists_record(
        self,
        consent_service: ConsentService,
        pipeline: PersonalSkillDataIngestionPipeline,
        skill_store: InMemoryPersonalSkillStore,
    ) -> None:
        granted = consent_service.grant(tenant_id=TENANT, subject_id=SUBJECT)
        record = pipeline.ingest(
            tenant_id=TENANT,
            subject_id=SUBJECT,
            skill_code="python",
            proficiency_level=4,
            evidence="assessment-42",
        )
        assert record.skill_code == "PYTHON"
        assert record.proficiency_level == 4
        assert record.consent_id == granted.id
        assert len(skill_store.records) == 1

    def test_batch_ingest_checks_consent_once_upfront(
        self,
        consent_service: ConsentService,
        pipeline: PersonalSkillDataIngestionPipeline,
        skill_store: InMemoryPersonalSkillStore,
    ) -> None:
        with pytest.raises(ConsentMissingError):
            pipeline.ingest_batch(
                tenant_id=TENANT,
                subject_id=SUBJECT,
                rows=[
                    {"skill_code": "SQL", "proficiency_level": 2},
                    {"skill_code": "PYTHON", "proficiency_level": 3},
                ],
            )
        assert skill_store.records == []

        consent_service.grant(tenant_id=TENANT, subject_id=SUBJECT)
        persisted = pipeline.ingest_batch(
            tenant_id=TENANT,
            subject_id=SUBJECT,
            rows=[
                {"skill_code": "SQL", "proficiency_level": 2},
                {"skill_code": "PYTHON", "proficiency_level": 3},
            ],
        )
        assert len(persisted) == 2
        assert len(skill_store.records) == 2

    def test_ingest_after_revoke_is_rejected(
        self,
        consent_service: ConsentService,
        pipeline: PersonalSkillDataIngestionPipeline,
        skill_store: InMemoryPersonalSkillStore,
    ) -> None:
        consent_service.grant(tenant_id=TENANT, subject_id=SUBJECT)
        pipeline.ingest(
            tenant_id=TENANT,
            subject_id=SUBJECT,
            skill_code="SQL",
            proficiency_level=2,
        )
        consent_service.revoke(tenant_id=TENANT, subject_id=SUBJECT)

        with pytest.raises(ConsentMissingError):
            pipeline.ingest(
                tenant_id=TENANT,
                subject_id=SUBJECT,
                skill_code="PYTHON",
                proficiency_level=3,
            )
        assert len(skill_store.records) == 1


class TestHttp422Mapping:
    """HTTP adapter maps ConsentMissingError to status 422."""

    def test_ingest_endpoint_returns_422_when_consent_missing(
        self,
        consent_service: ConsentService,
        pipeline: PersonalSkillDataIngestionPipeline,
    ) -> None:
        async def ingest_personal_skill(request: Request) -> JSONResponse:
            body = await request.json()
            try:
                record = pipeline.ingest(
                    tenant_id=UUID(body["tenant_id"]),
                    subject_id=UUID(body["subject_id"]),
                    skill_code=body["skill_code"],
                    proficiency_level=int(body["proficiency_level"]),
                )
            except ConsentMissingError as exc:
                return consent_error_response(exc)
            return JSONResponse(
                status_code=201,
                content={
                    "id": str(record.id),
                    "skill_code": record.skill_code,
                    "consent_id": str(record.consent_id),
                },
            )

        app = Starlette(
            routes=[
                Route(
                    "/api/v1/personal-skills",
                    ingest_personal_skill,
                    methods=["POST"],
                )
            ]
        )
        client = TestClient(app)

        missing = client.post(
            "/api/v1/personal-skills",
            json={
                "tenant_id": str(TENANT),
                "subject_id": str(SUBJECT),
                "skill_code": "PYTHON",
                "proficiency_level": 3,
            },
        )
        assert missing.status_code == 422
        payload = missing.json()
        assert payload["error"] == "consent_missing"
        assert payload["purpose"] == PERSONAL_SKILL_DATA_PURPOSE

        consent_service.grant(tenant_id=TENANT, subject_id=SUBJECT)
        ok = client.post(
            "/api/v1/personal-skills",
            json={
                "tenant_id": str(TENANT),
                "subject_id": str(SUBJECT),
                "skill_code": "PYTHON",
                "proficiency_level": 3,
            },
        )
        assert ok.status_code == 201
        assert ok.json()["skill_code"] == "PYTHON"
