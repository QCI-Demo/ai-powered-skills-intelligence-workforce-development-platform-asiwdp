"""Unit tests for ConsentService grant / revoke / validity queries."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from asiwdp_personal_data import (
    PERSONAL_SKILL_DATA_PURPOSE,
    ConsentService,
    ConsentStatus,
)
from asiwdp_personal_data.models import ConsentRecord

TENANT = UUID("22222222-2222-2222-2222-222222222222")
SUBJECT = UUID("11111111-1111-1111-1111-111111111111")


def test_grant_creates_valid_consent(consent_service: ConsentService) -> None:
    record = consent_service.grant(tenant_id=TENANT, subject_id=SUBJECT)
    assert record.status == ConsentStatus.GRANTED
    assert record.purpose == PERSONAL_SKILL_DATA_PURPOSE
    assert consent_service.has_valid_consent(
        tenant_id=TENANT, subject_id=SUBJECT
    )


def test_missing_consent_returns_false(consent_service: ConsentService) -> None:
    assert not consent_service.has_valid_consent(
        tenant_id=TENANT, subject_id=SUBJECT
    )
    assert (
        consent_service.get_valid_consent(tenant_id=TENANT, subject_id=SUBJECT)
        is None
    )


def test_revoked_consent_is_invalid(consent_service: ConsentService) -> None:
    consent_service.grant(tenant_id=TENANT, subject_id=SUBJECT)
    revoked = consent_service.revoke(tenant_id=TENANT, subject_id=SUBJECT)
    assert revoked is not None
    assert revoked.status == ConsentStatus.REVOKED
    assert not consent_service.has_valid_consent(
        tenant_id=TENANT, subject_id=SUBJECT
    )


def test_expired_consent_is_invalid(consent_service: ConsentService) -> None:
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    store = consent_service._store  # noqa: SLF001 — intentional for expired seed
    store.put(
        ConsentRecord(
            tenant_id=TENANT,
            subject_id=SUBJECT,
            purpose=PERSONAL_SKILL_DATA_PURPOSE,
            status=ConsentStatus.GRANTED,
            expires_at=past,
        )
    )
    assert not consent_service.has_valid_consent(
        tenant_id=TENANT, subject_id=SUBJECT
    )


def test_consent_is_tenant_and_subject_scoped(
    consent_service: ConsentService,
) -> None:
    other_tenant = UUID("44444444-4444-4444-4444-444444444444")
    other_subject = UUID("55555555-5555-5555-5555-555555555555")
    consent_service.grant(tenant_id=TENANT, subject_id=SUBJECT)

    assert consent_service.has_valid_consent(
        tenant_id=TENANT, subject_id=SUBJECT
    )
    assert not consent_service.has_valid_consent(
        tenant_id=other_tenant, subject_id=SUBJECT
    )
    assert not consent_service.has_valid_consent(
        tenant_id=TENANT, subject_id=other_subject
    )
