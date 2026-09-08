"""Shared fixtures for ingestion validation tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from asiwdp_ingestion import IngestionValidator, SchemaRegistry

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACTS_ROOT = REPO_ROOT / "contracts" / "ingestion"

TENANT_ID = "11111111-1111-1111-1111-111111111111"
OTHER_TENANT = "22222222-2222-2222-2222-222222222222"


def _consent() -> dict:
    return {
        "purpose": "skills_intelligence",
        "lawfulBasis": "legitimate_interest",
        "capturedAt": "2026-09-08T12:00:00Z",
        "version": "1.0",
        "dataSubjectId": "emp-1001",
    }


def _envelope(**overrides):
    base = {
        "tenantId": TENANT_ID,
        "sourceSystem": "workday",
        "sourceRecordId": "src-1",
        "idempotencyKey": "idem-1",
        "capturedAt": "2026-09-08T12:00:00Z",
        "consent": _consent(),
        "schemaVersion": "1.0.0",
        "correlationId": "corr-1",
    }
    base.update(overrides)
    return base


@pytest.fixture(scope="session")
def contracts_root() -> Path:
    assert CONTRACTS_ROOT.is_dir(), f"Missing contracts at {CONTRACTS_ROOT}"
    return CONTRACTS_ROOT


@pytest.fixture(scope="session")
def registry(contracts_root: Path) -> SchemaRegistry:
    return SchemaRegistry(contracts_root)


@pytest.fixture(scope="session")
def validator(registry: SchemaRegistry) -> IngestionValidator:
    return IngestionValidator(registry)


@pytest.fixture
def valid_employee() -> dict:
    return {
        **_envelope(),
        "employee": {
            "externalEmployeeId": "E-1001",
            "workEmail": "worker@example.com",
            "preferredName": "Alex",
            "jobTitle": "Engineer",
            "department": "Platform",
            "employmentStatus": "active",
            "hireDate": "2024-01-15",
            "locale": "en-US",
            "roleCodes": ["ENG-II"],
        },
    }


@pytest.fixture
def valid_role() -> dict:
    return {
        **_envelope(sourceSystem="successfactors", sourceRecordId="role-9"),
        "role": {
            "roleCode": "ENG-II",
            "title": "Software Engineer II",
            "description": "Builds services",
            "family": "Engineering",
            "level": "mid",
            "status": "active",
            "requiredSkillIds": ["aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"],
        },
    }


@pytest.fixture
def valid_learning_content() -> dict:
    return {
        **_envelope(sourceSystem="cornerstone", sourceRecordId="lc-42"),
        "content": {
            "contentId": "COURSE-42",
            "title": "Python Fundamentals",
            "contentType": "course",
            "status": "published",
            "locale": "en",
            "durationMinutes": 120,
            "provider": "Internal LMS",
            "skillIds": ["bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"],
            "tags": ["python", "beginner"],
        },
    }


@pytest.fixture
def valid_learner_activity() -> dict:
    return {
        **_envelope(sourceSystem="cornerstone", sourceRecordId="act-7"),
        "activity": {
            "externalEmployeeId": "E-1001",
            "contentId": "COURSE-42",
            "activityType": "completed",
            "occurredAt": "2026-09-07T18:30:00Z",
            "status": "completed",
            "progressPercent": 100,
            "score": 92.5,
            "timeSpentSeconds": 5400,
            "completionDate": "2026-09-07",
        },
    }
