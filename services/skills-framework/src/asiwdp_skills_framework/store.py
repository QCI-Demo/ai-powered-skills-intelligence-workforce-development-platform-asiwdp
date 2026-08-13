"""In-memory taxonomy store used for local/dev and unit tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Iterable
from uuid import UUID

from asiwdp_skills_framework.models import AuditEntry, Category, Proficiency, Skill


@dataclass
class TaxonomyStore:
    """Thread-safe in-memory persistence for taxonomy entities."""

    skills: dict[UUID, Skill] = field(default_factory=dict)
    categories: dict[UUID, Category] = field(default_factory=dict)
    proficiencies: dict[UUID, Proficiency] = field(default_factory=dict)
    audit_log: list[AuditEntry] = field(default_factory=list)
    _lock: RLock = field(default_factory=RLock, repr=False)

    def append_audit(self, entry: AuditEntry) -> AuditEntry:
        with self._lock:
            self.audit_log.append(entry)
            return entry

    def iter_skills(
        self, *, tenant_id: UUID, version: int | None = None
    ) -> Iterable[Skill]:
        with self._lock:
            items = list(self.skills.values())
        for item in items:
            if item.tenant_id != tenant_id:
                continue
            if version is not None and item.version != version:
                continue
            yield item

    def iter_categories(
        self, *, tenant_id: UUID, version: int | None = None
    ) -> Iterable[Category]:
        with self._lock:
            items = list(self.categories.values())
        for item in items:
            if item.tenant_id != tenant_id:
                continue
            if version is not None and item.version != version:
                continue
            yield item

    def iter_proficiencies(
        self, *, tenant_id: UUID, version: int | None = None
    ) -> Iterable[Proficiency]:
        with self._lock:
            items = list(self.proficiencies.values())
        for item in items:
            if item.tenant_id != tenant_id:
                continue
            if version is not None and item.version != version:
                continue
            yield item
