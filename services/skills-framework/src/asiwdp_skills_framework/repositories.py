"""Repository layer for skills, categories, proficiencies, and audit entries."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from asiwdp_skills_framework.models import AuditEntry, Category, Proficiency, Skill
from asiwdp_skills_framework.store import TaxonomyStore


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SkillRepository:
    def __init__(self, store: TaxonomyStore) -> None:
        self._store = store

    def create(self, skill: Skill) -> Skill:
        with self._store._lock:
            for existing in self._store.skills.values():
                if (
                    existing.tenant_id == skill.tenant_id
                    and existing.code == skill.code
                    and existing.version == skill.version
                ):
                    raise ValueError(
                        f"Skill code '{skill.code}' already exists for version {skill.version}"
                    )
            self._store.skills[skill.id] = skill
            return skill

    def get(self, *, tenant_id: UUID, skill_id: UUID) -> Skill | None:
        skill = self._store.skills.get(skill_id)
        if skill is None or skill.tenant_id != tenant_id:
            return None
        return skill

    def update(self, skill: Skill) -> Skill:
        with self._store._lock:
            skill.updated_at = _utcnow()
            self._store.skills[skill.id] = skill
            return skill

    def list(
        self,
        *,
        tenant_id: UUID,
        version: int | None = None,
        status: str | None = None,
        q: str | None = None,
        category: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Skill], int]:
        items = list(self._store.iter_skills(tenant_id=tenant_id, version=version))
        if status:
            items = [s for s in items if s.status == status]
        if category:
            items = [s for s in items if (s.category or "").lower() == category.lower()]
        if q:
            needle = q.lower()
            items = [
                s
                for s in items
                if needle in s.code.lower()
                or needle in s.name.lower()
                or needle in (s.description or "").lower()
            ]
        items.sort(key=lambda s: (s.code, s.version))
        total = len(items)
        return items[offset : offset + limit], total


class CategoryRepository:
    def __init__(self, store: TaxonomyStore) -> None:
        self._store = store

    def create(self, category: Category) -> Category:
        with self._store._lock:
            for existing in self._store.categories.values():
                if (
                    existing.tenant_id == category.tenant_id
                    and existing.code == category.code
                    and existing.version == category.version
                ):
                    raise ValueError(
                        f"Category code '{category.code}' already exists for version {category.version}"
                    )
            self._store.categories[category.id] = category
            return category

    def get(self, *, tenant_id: UUID, category_id: UUID) -> Category | None:
        category = self._store.categories.get(category_id)
        if category is None or category.tenant_id != tenant_id:
            return None
        return category

    def update(self, category: Category) -> Category:
        with self._store._lock:
            category.updated_at = _utcnow()
            self._store.categories[category.id] = category
            return category

    def list(
        self,
        *,
        tenant_id: UUID,
        version: int | None = None,
        status: str | None = None,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Category], int]:
        items = list(self._store.iter_categories(tenant_id=tenant_id, version=version))
        if status:
            items = [c for c in items if c.status == status]
        if q:
            needle = q.lower()
            items = [
                c
                for c in items
                if needle in c.code.lower()
                or needle in c.name.lower()
                or needle in (c.description or "").lower()
            ]
        items.sort(key=lambda c: (c.code, c.version))
        total = len(items)
        return items[offset : offset + limit], total


class ProficiencyRepository:
    def __init__(self, store: TaxonomyStore) -> None:
        self._store = store

    def create(self, proficiency: Proficiency) -> Proficiency:
        with self._store._lock:
            for existing in self._store.proficiencies.values():
                if (
                    existing.tenant_id == proficiency.tenant_id
                    and existing.version == proficiency.version
                    and (
                        existing.code == proficiency.code
                        or existing.level == proficiency.level
                    )
                ):
                    raise ValueError(
                        "Proficiency code/level conflict for tenant/version"
                    )
            self._store.proficiencies[proficiency.id] = proficiency
            return proficiency

    def get(self, *, tenant_id: UUID, proficiency_id: UUID) -> Proficiency | None:
        proficiency = self._store.proficiencies.get(proficiency_id)
        if proficiency is None or proficiency.tenant_id != tenant_id:
            return None
        return proficiency

    def update(self, proficiency: Proficiency) -> Proficiency:
        with self._store._lock:
            proficiency.updated_at = _utcnow()
            self._store.proficiencies[proficiency.id] = proficiency
            return proficiency

    def list(
        self,
        *,
        tenant_id: UUID,
        version: int | None = None,
        status: str | None = None,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Proficiency], int]:
        items = list(
            self._store.iter_proficiencies(tenant_id=tenant_id, version=version)
        )
        if status:
            items = [p for p in items if p.status == status]
        if q:
            needle = q.lower()
            items = [
                p
                for p in items
                if needle in p.code.lower()
                or needle in p.name.lower()
                or needle in (p.description or "").lower()
            ]
        items.sort(key=lambda p: (p.rank_order, p.level, p.version))
        total = len(items)
        return items[offset : offset + limit], total


class AuditRepository:
    def __init__(self, store: TaxonomyStore) -> None:
        self._store = store

    def write(
        self,
        *,
        tenant_id: UUID,
        version: int,
        entity_type: str,
        entity_id: UUID,
        action: str,
        actor_id: UUID | None = None,
        correlation_id: UUID | None = None,
        change_blob: dict[str, Any] | None = None,
        row_number: int | None = None,
    ) -> AuditEntry:
        entry = AuditEntry(
            id=uuid4(),
            tenant_id=tenant_id,
            version=version,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_id=actor_id,
            correlation_id=correlation_id,
            change_blob=change_blob or {},
            row_number=row_number,
        )
        return self._store.append_audit(entry)
