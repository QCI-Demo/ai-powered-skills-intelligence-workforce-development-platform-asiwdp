"""Domain models for consent and personal skill data."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

# Canonical processing purpose for personal skill profile / proficiency data.
PERSONAL_SKILL_DATA_PURPOSE = "personal_skill_data_processing"


class ConsentStatus(str, Enum):
    """Lifecycle status of a consent grant."""

    GRANTED = "granted"
    REVOKED = "revoked"
    EXPIRED = "expired"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class ConsentRecord:
    """Tenant-scoped consent grant for a data subject and purpose."""

    tenant_id: UUID
    subject_id: UUID
    purpose: str
    status: ConsentStatus = ConsentStatus.GRANTED
    id: UUID = field(default_factory=uuid4)
    granted_at: datetime = field(default_factory=_utcnow)
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    policy_version: str = "1.0"
    source: str = "api"
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_valid(self, *, at: datetime | None = None) -> bool:
        """Return True when the grant is active for processing at ``at`` (UTC)."""
        moment = at or _utcnow()
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        if self.status != ConsentStatus.GRANTED:
            return False
        if self.revoked_at is not None and self.revoked_at <= moment:
            return False
        if self.expires_at is not None:
            expires = self.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires <= moment:
                return False
        return True


@dataclass(frozen=True, slots=True)
class PersonalSkillRecord:
    """Persisted personal skill / proficiency datum for a subject."""

    tenant_id: UUID
    subject_id: UUID
    skill_code: str
    proficiency_level: int
    id: UUID = field(default_factory=uuid4)
    evidence: str | None = None
    source: str = "ingestion"
    ingested_at: datetime = field(default_factory=_utcnow)
    consent_id: UUID | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
