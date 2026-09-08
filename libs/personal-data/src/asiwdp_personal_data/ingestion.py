"""Personal skill data ingestion pipeline with consent pre-processing."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID, uuid4

from asiwdp_personal_data.consent_service import ConsentService
from asiwdp_personal_data.errors import ConsentMissingError
from asiwdp_personal_data.models import (
    PERSONAL_SKILL_DATA_PURPOSE,
    PersonalSkillRecord,
)


class PersonalSkillStore(Protocol):
    """Persistence port for personal skill records."""

    def save(self, record: PersonalSkillRecord) -> PersonalSkillRecord: ...

    def list_for_subject(
        self,
        *,
        tenant_id: UUID,
        subject_id: UUID,
    ) -> list[PersonalSkillRecord]: ...


class InMemoryPersonalSkillStore:
    """Process-local personal skill store for tests and local development."""

    def __init__(self) -> None:
        self._records: dict[UUID, PersonalSkillRecord] = {}

    def save(self, record: PersonalSkillRecord) -> PersonalSkillRecord:
        self._records[record.id] = record
        return record

    def list_for_subject(
        self,
        *,
        tenant_id: UUID,
        subject_id: UUID,
    ) -> list[PersonalSkillRecord]:
        return [
            r
            for r in self._records.values()
            if r.tenant_id == tenant_id and r.subject_id == subject_id
        ]

    @property
    def records(self) -> list[PersonalSkillRecord]:
        return list(self._records.values())


class ConsentGuard:
    """
    Pre-processing step that queries ConsentService before personal data writes.

    Raises ConsentMissingError (HTTP 422) when no valid consent record exists.
    """

    def __init__(
        self,
        consent_service: ConsentService,
        *,
        purpose: str = PERSONAL_SKILL_DATA_PURPOSE,
    ) -> None:
        self._consent = consent_service
        self._purpose = purpose

    @property
    def purpose(self) -> str:
        return self._purpose

    def require_valid_consent(
        self,
        *,
        tenant_id: UUID,
        subject_id: UUID,
    ) -> UUID:
        """
        Verify a valid consent grant exists for the subject.

        Returns the consent record id when present; raises ConsentMissingError
        otherwise (mapped to HTTP 422 by the HTTP adapter).
        """
        record = self._consent.get_valid_consent(
            tenant_id=tenant_id,
            subject_id=subject_id,
            purpose=self._purpose,
        )
        if record is None:
            raise ConsentMissingError(
                tenant_id=tenant_id,
                subject_id=subject_id,
                purpose=self._purpose,
            )
        return record.id


class PersonalSkillDataIngestionPipeline:
    """
    Mutating ingestion path for personal skill data.

    Flow:
      1. ConsentGuard queries ConsentService (pre-processing).
      2. On missing consent → ConsentMissingError (HTTP 422); nothing persisted.
      3. On valid consent → persist PersonalSkillRecord with consent_id linkage.
    """

    def __init__(
        self,
        *,
        consent_service: ConsentService,
        skill_store: PersonalSkillStore,
        purpose: str = PERSONAL_SKILL_DATA_PURPOSE,
    ) -> None:
        self._guard = ConsentGuard(consent_service, purpose=purpose)
        self._skills = skill_store

    @property
    def guard(self) -> ConsentGuard:
        return self._guard

    def ingest(
        self,
        *,
        tenant_id: UUID,
        subject_id: UUID,
        skill_code: str,
        proficiency_level: int,
        evidence: str | None = None,
        source: str = "ingestion",
        attributes: dict[str, Any] | None = None,
    ) -> PersonalSkillRecord:
        consent_id = self._guard.require_valid_consent(
            tenant_id=tenant_id,
            subject_id=subject_id,
        )
        record = PersonalSkillRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            subject_id=subject_id,
            skill_code=skill_code.strip().upper(),
            proficiency_level=proficiency_level,
            evidence=evidence,
            source=source,
            consent_id=consent_id,
            attributes=dict(attributes or {}),
        )
        return self._skills.save(record)

    def ingest_batch(
        self,
        *,
        tenant_id: UUID,
        subject_id: UUID,
        rows: list[dict[str, Any]],
    ) -> list[PersonalSkillRecord]:
        """
        Ingest multiple personal skill rows for one subject.

        Consent is checked once up front; if missing, no rows are persisted.
        """
        consent_id = self._guard.require_valid_consent(
            tenant_id=tenant_id,
            subject_id=subject_id,
        )
        persisted: list[PersonalSkillRecord] = []
        for row in rows:
            record = PersonalSkillRecord(
                id=uuid4(),
                tenant_id=tenant_id,
                subject_id=subject_id,
                skill_code=str(row["skill_code"]).strip().upper(),
                proficiency_level=int(row["proficiency_level"]),
                evidence=row.get("evidence"),
                source=str(row.get("source") or "batch_ingestion"),
                consent_id=consent_id,
                attributes=dict(row.get("attributes") or {}),
            )
            persisted.append(self._skills.save(record))
        return persisted
