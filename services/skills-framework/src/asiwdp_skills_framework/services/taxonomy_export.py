"""Streaming taxonomy export (CSV / JSON) with tenant + version filters.

Exposes current or historic snapshots via GET /taxonomy/export.
Format negotiated through the Accept header (or `format` query override).
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Callable, Iterator, Literal
from uuid import UUID

from asiwdp_skills_framework.repositories import (
    CategoryRepository,
    ProficiencyRepository,
    SkillRepository,
)

ExportFormat = Literal["json", "csv"]

# Page size for repository reads while streaming large datasets.
_PAGE_SIZE = 500

_CSV_FIELDNAMES = [
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
        """Negotiate CSV vs JSON from query override or Accept header."""
        if format_query:
            fmt = format_query.lower().strip()
            if fmt in {"json", "csv"}:
                return fmt  # type: ignore[return-value]
            raise ValueError("format query must be json or csv")

        # Prefer the first concrete media type when clients send quality lists.
        accept_raw = (accept or "application/json").lower()
        for part in accept_raw.split(","):
            media = part.split(";", 1)[0].strip()
            if media in {"text/csv", "application/csv"}:
                return "csv"
            if media == "application/json":
                return "json"
            if media in {"*/*", ""}:
                return "json"
            if media == "text/plain":
                return "csv"

        if "text/csv" in accept_raw or "application/csv" in accept_raw:
            return "csv"
        if "application/json" in accept_raw or "*/*" in accept_raw:
            return "json"
        raise ValueError(f"Unsupported Accept header: {accept}")

    def _paginate(
        self,
        list_fn: Callable[..., tuple[list[Any], int]],
        *,
        tenant_id: UUID,
        version: int | None,
    ) -> Iterator[Any]:
        """Yield repository rows in pages to avoid loading entire datasets."""
        offset = 0
        while True:
            items, total = list_fn(
                tenant_id=tenant_id,
                version=version,
                limit=_PAGE_SIZE,
                offset=offset,
            )
            if not items:
                break
            yield from items
            offset += len(items)
            if offset >= total:
                break

    def iter_records(
        self,
        *,
        tenant_id: UUID,
        version: int | None,
    ) -> Iterator[dict[str, Any]]:
        """Yield flat taxonomy records filtered by tenant_id and optional version."""
        for category in self._paginate(
            self._categories.list, tenant_id=tenant_id, version=version
        ):
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

        for skill in self._paginate(
            self._skills.list, tenant_id=tenant_id, version=version
        ):
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

        for proficiency in self._paginate(
            self._proficiencies.list, tenant_id=tenant_id, version=version
        ):
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
        """Stream a JSON document incrementally for large datasets."""
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
        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer, fieldnames=_CSV_FIELDNAMES, extrasaction="ignore"
        )
        writer.writeheader()
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)

        for record in self.iter_records(tenant_id=tenant_id, version=version):
            writer.writerow(record)
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)
