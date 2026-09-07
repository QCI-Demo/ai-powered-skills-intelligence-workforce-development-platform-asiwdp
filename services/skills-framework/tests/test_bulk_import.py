"""Tests for bulk CSV/JSON import validation service."""

from __future__ import annotations

import io
import json
from uuid import UUID

from asiwdp_skills_framework.repositories import (
    AuditRepository,
    CategoryRepository,
    ProficiencyRepository,
    SkillRepository,
)
from asiwdp_skills_framework.services.bulk_import import BulkImportValidationService
from asiwdp_skills_framework.store import TaxonomyStore

TENANT = UUID("22222222-2222-2222-2222-222222222222")


def _service(store: TaxonomyStore | None = None) -> tuple[BulkImportValidationService, TaxonomyStore]:
    store = store or TaxonomyStore()
    service = BulkImportValidationService(
        skills=SkillRepository(store),
        categories=CategoryRepository(store),
        proficiencies=ProficiencyRepository(store),
        audit=AuditRepository(store),
    )
    return service, store


def test_csv_import_validates_and_persists_rows():
    service, store = _service()
    csv_body = (
        "tenant_id,version,code,name,description,category,status\n"
        f"{TENANT},1,PYTHON,Python Programming,Write Python,Technical,active\n"
        f"{TENANT},1,SQL,SQL,Query data,Technical,active\n"
    )
    report = service.import_stream(
        io.StringIO(csv_body),
        tenant_id=TENANT,
        version=1,
        entity_type="skill",
        format="csv",
    )
    assert report.total_rows == 2
    assert report.success_count == 2
    assert report.error_count == 0
    assert report.audit_entries == 2
    assert len(store.skills) == 2
    assert len(store.audit_log) == 2
    assert all(e.action == "IMPORT" for e in store.audit_log)


def test_csv_import_aggregates_row_errors():
    service, _ = _service()
    csv_body = (
        "tenant_id,version,code,name\n"
        f"{TENANT},1,OK,Valid Skill\n"
        f"11111111-1111-1111-1111-111111111111,1,BAD,Wrong Tenant\n"
        f"{TENANT},2,VER,Wrong Version\n"
        f"{TENANT},1,,Missing Code\n"
    )
    report = service.import_stream(
        io.StringIO(csv_body),
        tenant_id=TENANT,
        version=1,
        entity_type="skill",
        format="csv",
    )
    assert report.success_count == 1
    assert report.error_count == 3
    assert report.total_rows == 4
    assert any("tenant_id" in e.errors[0] for e in report.errors)


def test_ndjson_import_line_by_line():
    service, store = _service()
    lines = [
        json.dumps(
            {
                "tenant_id": str(TENANT),
                "version": 1,
                "code": "FOUNDATIONAL",
                "name": "Foundational",
            }
        ),
        json.dumps(
            {
                "tenant_id": str(TENANT),
                "version": 1,
                "code": "TECHNICAL",
                "name": "Technical",
            }
        ),
    ]
    report = service.import_stream(
        io.StringIO("\n".join(lines) + "\n"),
        tenant_id=TENANT,
        version=1,
        entity_type="category",
        format="ndjson",
    )
    assert report.success_count == 2
    assert len(store.categories) == 2


def test_json_array_import_proficiencies():
    service, store = _service()
    payload = [
        {
            "tenant_id": str(TENANT),
            "version": 1,
            "level": 1,
            "code": "AWARE",
            "name": "Awareness",
            "rank_order": 1,
        },
        {
            "tenant_id": str(TENANT),
            "version": 1,
            "level": 2,
            "code": "WORKING",
            "name": "Working",
            "rank_order": 2,
        },
    ]
    report = service.import_stream(
        io.StringIO(json.dumps(payload)),
        tenant_id=TENANT,
        version=1,
        entity_type="proficiency",
        format="json",
    )
    assert report.success_count == 2
    assert report.version == 1
    assert len(store.proficiencies) == 2
