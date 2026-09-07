"""Bulk CSV/JSON import with row-level validation and audit reporting.

Story task: 188869f2-8779-493f-a23f-c710b214c40e
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any, BinaryIO, Iterator, TextIO
from uuid import UUID, uuid4

from pydantic import ValidationError

from asiwdp_skills_framework.models import Category, Proficiency, Skill
from asiwdp_skills_framework.repositories import (
    AuditRepository,
    CategoryRepository,
    ProficiencyRepository,
    SkillRepository,
)
from asiwdp_skills_framework.schemas.responses import ImportReport, ImportRowError
from asiwdp_skills_framework.validation import validate_import_row


ENTITY_TYPES = frozenset({"skill", "category", "proficiency"})


def _as_text_stream(file_obj: BinaryIO | TextIO[str]) -> TextIO[str]:
    if isinstance(file_obj, io.TextIOBase):
        return file_obj
    return io.TextIOWrapper(file_obj, encoding="utf-8", newline="")


def _iter_csv_rows(stream: TextIO[str]) -> Iterator[tuple[int, dict[str, Any]]]:
    """Read CSV line-by-line via DictReader (stream-friendly)."""
    reader = csv.DictReader(stream)
    if not reader.fieldnames:
        raise ValueError("CSV file is missing a header row")
    for row_number, row in enumerate(reader, start=2):  # header is line 1
        cleaned = {
            (k or "").strip(): (v.strip() if isinstance(v, str) else v)
            for k, v in row.items()
            if k is not None
        }
        yield row_number, cleaned


def _iter_json_rows(stream: TextIO[str]) -> Iterator[tuple[int, dict[str, Any]]]:
    """
    Support:
      - JSON array of objects
      - NDJSON (one JSON object per line)
    For arrays, content is loaded once; NDJSON is read line-by-line.
    """
    # Peek first non-whitespace character to decide format
    while True:
        pos = stream.tell()
        ch = stream.read(1)
        if not ch:
            return
        if not ch.isspace():
            stream.seek(pos)
            break

    if ch == "[":
        payload = json.load(stream)
        if not isinstance(payload, list):
            raise ValueError("JSON array import must be a list of objects")
        for idx, item in enumerate(payload, start=1):
            if not isinstance(item, dict):
                yield idx, {"_invalid": item}
            else:
                yield idx, item
        return

    # NDJSON / line-delimited JSON
    stream.seek(pos)
    for line_number, line in enumerate(stream, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            item = json.loads(stripped)
        except json.JSONDecodeError as exc:
            yield line_number, {"_parse_error": str(exc), "_raw": stripped}
            continue
        if not isinstance(item, dict):
            yield line_number, {"_invalid": item}
        else:
            yield line_number, item


def _coerce_optional_uuid(value: Any) -> UUID | None:
    if value is None or value == "":
        return None
    return UUID(str(value))


def _coerce_int(value: Any, field: str) -> int:
    if value is None or value == "":
        raise ValueError(f"{field} is required")
    return int(value)


class BulkImportValidationService:
    """Parse CSV/JSON streams, validate rows, persist successes, emit reports."""

    def __init__(
        self,
        *,
        skills: SkillRepository,
        categories: CategoryRepository,
        proficiencies: ProficiencyRepository,
        audit: AuditRepository,
    ) -> None:
        self._skills = skills
        self._categories = categories
        self._proficiencies = proficiencies
        self._audit = audit

    def import_stream(
        self,
        file_obj: BinaryIO | TextIO[str],
        *,
        tenant_id: UUID,
        version: int,
        entity_type: str,
        format: str,
        actor_id: UUID | None = None,
        correlation_id: UUID | None = None,
    ) -> ImportReport:
        if entity_type not in ENTITY_TYPES:
            raise ValueError(
                f"Unsupported entity_type '{entity_type}'. "
                f"Expected one of: {sorted(ENTITY_TYPES)}"
            )
        fmt = format.lower().strip()
        if fmt not in {"csv", "json", "ndjson"}:
            raise ValueError("format must be csv, json, or ndjson")

        import_id = uuid4()
        correlation_id = correlation_id or import_id
        text = _as_text_stream(file_obj)

        if fmt == "csv":
            rows = _iter_csv_rows(text)
        else:
            rows = _iter_json_rows(text)

        errors: list[ImportRowError] = []
        created_ids: list[UUID] = []
        success_count = 0
        skipped_count = 0
        total_rows = 0
        audit_count = 0

        for row_number, raw in rows:
            total_rows += 1

            if "_parse_error" in raw:
                errors.append(
                    ImportRowError(
                        row_number=row_number,
                        entity_type=entity_type,
                        errors=[f"JSON parse error: {raw['_parse_error']}"],
                        raw={"_raw": raw.get("_raw")},
                    )
                )
                continue
            if "_invalid" in raw:
                errors.append(
                    ImportRowError(
                        row_number=row_number,
                        entity_type=entity_type,
                        errors=["Row must be a JSON object"],
                        raw={"value": raw["_invalid"]},
                    )
                )
                continue

            # Normalize empty strings to None for optional fields
            row = {k: (None if v == "" else v) for k, v in raw.items()}

            field_errors = validate_import_row(
                row,
                entity_type=entity_type,
                expected_tenant_id=tenant_id,
                expected_version=version,
            )
            if field_errors:
                errors.append(
                    ImportRowError(
                        row_number=row_number,
                        entity_type=entity_type,
                        code=str(row.get("code") or "") or None,
                        errors=field_errors,
                        raw=row,
                    )
                )
                continue

            try:
                entity_id = self._persist_row(
                    entity_type=entity_type,
                    row=row,
                    tenant_id=tenant_id,
                    version=version,
                )
            except (ValueError, ValidationError, KeyError, TypeError) as exc:
                errors.append(
                    ImportRowError(
                        row_number=row_number,
                        entity_type=entity_type,
                        code=str(row.get("code") or "") or None,
                        errors=[str(exc)],
                        raw=row,
                    )
                )
                continue

            success_count += 1
            created_ids.append(entity_id)
            self._audit.write(
                tenant_id=tenant_id,
                version=version,
                entity_type=entity_type,
                entity_id=entity_id,
                action="IMPORT",
                actor_id=actor_id,
                correlation_id=correlation_id,
                change_blob={"row": row, "import_id": str(import_id)},
                row_number=row_number,
            )
            audit_count += 1

        return ImportReport(
            import_id=import_id,
            tenant_id=tenant_id,
            version=version,
            format=fmt,
            entity_type=entity_type,
            total_rows=total_rows,
            success_count=success_count,
            error_count=len(errors),
            skipped_count=skipped_count,
            errors=errors,
            created_ids=created_ids,
            audit_entries=audit_count,
        )

    def _persist_row(
        self,
        *,
        entity_type: str,
        row: dict[str, Any],
        tenant_id: UUID,
        version: int,
    ) -> UUID:
        row_tenant = UUID(str(row.get("tenant_id") or tenant_id))
        row_version = int(row.get("version") or version)

        if entity_type == "skill":
            skill = Skill(
                tenant_id=row_tenant,
                version=row_version,
                code=str(row["code"]),
                name=str(row["name"]),
                description=row.get("description"),
                category=row.get("category"),
                parent_skill_id=_coerce_optional_uuid(row.get("parent_skill_id")),
                status=str(row.get("status") or "active"),
            )
            return self._skills.create(skill).id

        if entity_type == "category":
            category = Category(
                tenant_id=row_tenant,
                version=row_version,
                code=str(row["code"]),
                name=str(row["name"]),
                description=row.get("description"),
                parent_category_id=_coerce_optional_uuid(row.get("parent_category_id")),
                status=str(row.get("status") or "active"),
            )
            return self._categories.create(category).id

        proficiency = Proficiency(
            tenant_id=row_tenant,
            version=row_version,
            level=_coerce_int(row.get("level"), "level"),
            code=str(row["code"]),
            name=str(row["name"]),
            description=row.get("description"),
            rank_order=_coerce_int(row.get("rank_order"), "rank_order"),
            status=str(row.get("status") or "active"),
        )
        return self._proficiencies.create(proficiency).id
