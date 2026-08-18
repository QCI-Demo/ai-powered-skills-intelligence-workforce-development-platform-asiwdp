"""Streaming taxonomy export (CSV / JSON) with tenant + version filters.

Story task: 5c3216e8-680c-455b-adbc-fb8c9cfebea0
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Iterator, Literal
from uuid import UUID

from asiwdp_skills_framework.repositories import (
    CategoryRepository,
    ProficiencyRepository,
    SkillRepository,
)

ExportFormat = Literal["json", "csv"]


class TaxonomyExportService:
    """Stream current or historic taxonomy snapshots."""

    def __init__(
        self,
        *,
        skills: SkillRepository,
        categories: CategoryRepository,
        proficiencies: ProficiencyRepository,
    ) -> None:
        self._skills = skills
        self._categories = categories
        self._proficiencies = proficiencies

    def resolve_format(
        self,
        *,
        accept: str | None,
        format_query: str | None,
    ) -> ExportFormat:
        if format_query:
            fmt = format_query.lower().strip()
            if fmt in {"json", "csv"}:
                return fmt  # type: ignore[return-value]
            raise ValueError("format query must be json or csv")

        accept = (accept or "application/json").lower()
        if "text/csv" in accept or "application/csv" in accept:
            return "csv"
        if "application/json" in accept or "*/*" in accept or accept == "":
            return "json"
        if "text/plain" in accept:
            return "csv"
        raise ValueError(f"Unsupported Accept header: {accept}")

    def iter_records(
        self,
        *,
        tenant_id: UUID,
        version: int | None,
    ) -> Iterator[dict[str, Any]]:
        """Yield flat taxonomy records filtered by tenant_id and optional version."""
        categories, _ = self._categories.list(
            tenant_id=tenant_id, version=version, limit=10_000, offset=0
        )
        for category in categories:
            yield {
                "entity_type": "category",
                "id": str(category.id),
                "tenant_id": str(category.tenant_id),
                "version": category.version,
                "code": category.code,
                "name": category.name,
                "description": category.description or "",
                "status": category.status,
                "parent_id": str(category.parent_category_id)
                if category.parent_category_id
                else "",
                "level": "",
                "rank_order": "",
                "category": "",
            }

        skills, _ = self._skills.list(
            tenant_id=tenant_id, version=version, limit=10_000, offset=0
        )
        for skill in skills:
            yield {
                "entity_type": "skill",
                "id": str(skill.id),
                "tenant_id": str(skill.tenant_id),
                "version": skill.version,
                "code": skill.code,
                "name": skill.name,
                "description": skill.description or "",
                "status": skill.status,
                "parent_id": str(skill.parent_skill_id) if skill.parent_skill_id else "",
                "level": "",
                "rank_order": "",
                "category": skill.category or "",
            }

        proficiencies, _ = self._proficiencies.list(
            tenant_id=tenant_id, version=version, limit=10_000, offset=0
        )
        for proficiency in proficiencies:
            yield {
                "entity_type": "proficiency",
                "id": str(proficiency.id),
                "tenant_id": str(proficiency.tenant_id),
                "version": proficiency.version,
                "code": proficiency.code,
                "name": proficiency.name,
                "description": proficiency.description or "",
                "status": proficiency.status,
                "parent_id": "",
                "level": proficiency.level,
                "rank_order": proficiency.rank_order,
                "category": "",
            }

    def stream_json(
        self, *, tenant_id: UUID, version: int | None
    ) -> Iterator[str]:
        """Stream a JSON array incrementally for large datasets."""
        yield '{"tenant_id":%s,"version":%s,"items":[' % (
            json.dumps(str(tenant_id)),
            json.dumps(version),
        )
        first = True
        for record in self.iter_records(tenant_id=tenant_id, version=version):
            chunk = json.dumps(record, separators=(",", ":"))
            if first:
                yield chunk
                first = False
            else:
                yield "," + chunk
        yield "]}"

    def stream_csv(
        self, *, tenant_id: UUID, version: int | None
    ) -> Iterator[str]:
        """Stream CSV rows (header + data) incrementally."""
        fieldnames = [
            "entity_type",
            "id",
            "tenant_id",
            "version",
            "code",
            "name",
            "description",
            "status",
            "parent_id",
            "level",
            "rank_order",
            "category",
        ]
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)

        for record in self.iter_records(tenant_id=tenant_id, version=version):
            writer.writerow(record)
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)
