"""Shared fixtures for asiwdp-personal-data tests."""

from __future__ import annotations

from uuid import UUID

import pytest

from asiwdp_personal_data import (
    ConsentService,
    InMemoryConsentStore,
    InMemoryPersonalSkillStore,
    PersonalSkillDataIngestionPipeline,
)

TENANT_ID = UUID("22222222-2222-2222-2222-222222222222")
SUBJECT_ID = UUID("11111111-1111-1111-1111-111111111111")
OTHER_SUBJECT = UUID("33333333-3333-3333-3333-333333333333")


@pytest.fixture
def consent_store() -> InMemoryConsentStore:
    return InMemoryConsentStore()


@pytest.fixture
def consent_service(consent_store: InMemoryConsentStore) -> ConsentService:
    return ConsentService(consent_store)


@pytest.fixture
def skill_store() -> InMemoryPersonalSkillStore:
    return InMemoryPersonalSkillStore()


@pytest.fixture
def pipeline(
    consent_service: ConsentService,
    skill_store: InMemoryPersonalSkillStore,
) -> PersonalSkillDataIngestionPipeline:
    return PersonalSkillDataIngestionPipeline(
        consent_service=consent_service,
        skill_store=skill_store,
    )
