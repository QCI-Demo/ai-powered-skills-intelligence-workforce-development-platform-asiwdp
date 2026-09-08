"""ConsentService: query and manage tenant-scoped consent records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID, uuid4

from asiwdp_personal_data.models import (
    PERSONAL_SKILL_DATA_PURPOSE,
    ConsentRecord,
    ConsentStatus,
)


class ConsentStore(Protocol):
    """Persistence port for consent records."""

    def put(self, record: ConsentRecord) -> ConsentRecord: ...

    def find_active(
        self,
        *,
        tenant_id: UUID,
        subject_id: UUID,
        purpose: str,
    ) -> ConsentRecord | None: ...

    def list_for_subject(
        self,
        *,
        tenant_id: UUID,
        subject_id: UUID,
    ) -> list[ConsentRecord]: ...


class InMemoryConsentStore:
    """Process-local consent store for unit tests and local development."""

    def __init__(self) -> None:
        self._records: dict[UUID, ConsentRecord] = {}

    def put(self, record: ConsentRecord) -> ConsentRecord:
        self._records[record.id] = record
        return record

    def find_active(
        self,
        *,
        tenant_id: UUID,
        subject_id: UUID,
        purpose: str,
    ) -> ConsentRecord | None:
        candidates = [
            r
            for r in self._records.values()
            if r.tenant_id == tenant_id
            and r.subject_id == subject_id
            and r.purpose == purpose
            and r.is_valid()
        ]
        if not candidates:
            return None
        # Prefer the most recently granted valid record.
        return max(candidates, key=lambda r: r.granted_at)

    def list_for_subject(
        self,
        *,
        tenant_id: UUID,
        subject_id: UUID,
    ) -> list[ConsentRecord]:
        return [
            r
            for r in self._records.values()
            if r.tenant_id == tenant_id and r.subject_id == subject_id
        ]


class ConsentService:
    """Application service for recording and verifying consent grants."""

    def __init__(self, store: ConsentStore) -> None:
        self._store = store

    def grant(
        self,
        *,
        tenant_id: UUID,
        subject_id: UUID,
        purpose: str = PERSONAL_SKILL_DATA_PURPOSE,
        expires_at: datetime | None = None,
        policy_version: str = "1.0",
        source: str = "api",
    ) -> ConsentRecord:
        record = ConsentRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            subject_id=subject_id,
            purpose=purpose,
            status=ConsentStatus.GRANTED,
            granted_at=datetime.now(timezone.utc),
            expires_at=expires_at,
            policy_version=policy_version,
            source=source,
        )
        return self._store.put(record)

    def revoke(
        self,
        *,
        tenant_id: UUID,
        subject_id: UUID,
        purpose: str = PERSONAL_SKILL_DATA_PURPOSE,
    ) -> ConsentRecord | None:
        existing = self._store.find_active(
            tenant_id=tenant_id,
            subject_id=subject_id,
            purpose=purpose,
        )
        if existing is None:
            return None
        revoked = ConsentRecord(
            id=existing.id,
            tenant_id=existing.tenant_id,
            subject_id=existing.subject_id,
            purpose=existing.purpose,
            status=ConsentStatus.REVOKED,
            granted_at=existing.granted_at,
            expires_at=existing.expires_at,
            revoked_at=datetime.now(timezone.utc),
            policy_version=existing.policy_version,
            source=existing.source,
            metadata=dict(existing.metadata),
        )
        return self._store.put(revoked)

    def get_valid_consent(
        self,
        *,
        tenant_id: UUID,
        subject_id: UUID,
        purpose: str = PERSONAL_SKILL_DATA_PURPOSE,
        at: datetime | None = None,
    ) -> ConsentRecord | None:
        record = self._store.find_active(
            tenant_id=tenant_id,
            subject_id=subject_id,
            purpose=purpose,
        )
        if record is None:
            return None
        if not record.is_valid(at=at):
            return None
        return record

    def has_valid_consent(
        self,
        *,
        tenant_id: UUID,
        subject_id: UUID,
        purpose: str = PERSONAL_SKILL_DATA_PURPOSE,
        at: datetime | None = None,
    ) -> bool:
        return (
            self.get_valid_consent(
                tenant_id=tenant_id,
                subject_id=subject_id,
                purpose=purpose,
                at=at,
            )
            is not None
        )
