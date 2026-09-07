"""Focused tests for GET /api/v1/taxonomy/export streaming endpoint."""

from __future__ import annotations

import csv
import io
import json
from uuid import UUID

from asiwdp_skills_framework.models import Skill
from asiwdp_skills_framework.repositories import (
    CategoryRepository,
    ProficiencyRepository,
    SkillRepository,
)
from asiwdp_skills_framework.services.taxonomy_export import TaxonomyExportService
from asiwdp_skills_framework.store import TaxonomyStore

DEMO_TENANT = "22222222-2222-2222-2222-222222222222"
OTHER_TENANT = "11111111-1111-1111-1111-111111111111"


def _seed_taxonomy(client, tenant_headers, *, version: int = 1) -> None:
    headers = {**tenant_headers, "X-Taxonomy-Version": str(version)}
    assert (
        client.post(
            "/api/v1/categories",
            headers=headers,
            json={"code": f"TECH-V{version}", "name": f"Technical v{version}"},
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/v1/skills",
            headers=headers,
            json={
                "code": f"SQL-V{version}",
                "name": f"SQL v{version}",
                "category": "Technical",
            },
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/v1/proficiencies",
            headers=headers,
            json={
                "level": version,
                "code": f"AWARE-V{version}",
                "name": f"Awareness v{version}",
                "rank_order": version,
            },
        ).status_code
        == 201
    )


def test_export_json_via_accept_header(client, tenant_headers):
    _seed_taxonomy(client, tenant_headers, version=1)

    response = client.get(
        "/api/v1/taxonomy/export",
        headers={**tenant_headers, "Accept": "application/json"},
        params={"tenant_id": DEMO_TENANT, "version": 1},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert "attachment" in response.headers.get("content-disposition", "")
    payload = response.json()
    assert payload["tenant_id"] == DEMO_TENANT
    assert payload["version"] == 1
    assert len(payload["items"]) == 3
    entity_types = {item["entity_type"] for item in payload["items"]}
    assert entity_types == {"category", "skill", "proficiency"}
    assert all(item["tenant_id"] == DEMO_TENANT for item in payload["items"])
    assert all(item["version"] == 1 for item in payload["items"])


def test_export_csv_via_accept_header(client, tenant_headers):
    _seed_taxonomy(client, tenant_headers, version=1)

    response = client.get(
        "/api/v1/taxonomy/export",
        headers={**tenant_headers, "Accept": "text/csv"},
        params={"version": 1},
    )

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == 3
    assert {row["entity_type"] for row in rows} == {
        "category",
        "skill",
        "proficiency",
    }


def test_export_format_query_overrides_accept(client, tenant_headers):
    _seed_taxonomy(client, tenant_headers, version=1)

    response = client.get(
        "/api/v1/taxonomy/export",
        headers={**tenant_headers, "Accept": "application/json"},
        params={"format": "csv", "version": 1},
    )

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert response.text.startswith("entity_type,")


def test_export_filters_historic_version(client, tenant_headers):
    _seed_taxonomy(client, tenant_headers, version=1)
    _seed_taxonomy(client, tenant_headers, version=2)

    v1 = client.get(
        "/api/v1/taxonomy/export",
        headers={**tenant_headers, "Accept": "application/json"},
        params={"version": 1},
    )
    v2 = client.get(
        "/api/v1/taxonomy/export",
        headers={**tenant_headers, "Accept": "application/json"},
        params={"version": 2},
    )

    assert v1.status_code == 200
    assert v2.status_code == 200
    assert v1.json()["version"] == 1
    assert v2.json()["version"] == 2
    assert all(item["version"] == 1 for item in v1.json()["items"])
    assert all(item["version"] == 2 for item in v2.json()["items"])
    assert {item["code"] for item in v1.json()["items"]} == {
        "TECH-V1",
        "SQL-V1",
        "AWARE-V1",
    }
    assert {item["code"] for item in v2.json()["items"]} == {
        "TECH-V2",
        "SQL-V2",
        "AWARE-V2",
    }


def test_export_defaults_to_header_version_when_query_omitted(client, tenant_headers):
    _seed_taxonomy(client, tenant_headers, version=1)
    _seed_taxonomy(client, tenant_headers, version=2)

    response = client.get(
        "/api/v1/taxonomy/export",
        headers={
            **tenant_headers,
            "X-Taxonomy-Version": "2",
            "Accept": "application/json",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == 2
    assert len(payload["items"]) == 3
    assert all(item["version"] == 2 for item in payload["items"])


def test_export_rejects_cross_tenant_filter(client, tenant_headers):
    response = client.get(
        "/api/v1/taxonomy/export",
        headers=tenant_headers,
        params={"tenant_id": OTHER_TENANT},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "tenant_mismatch"


def test_export_rejects_unsupported_accept(client, tenant_headers):
    response = client.get(
        "/api/v1/taxonomy/export",
        headers={**tenant_headers, "Accept": "application/xml"},
    )
    assert response.status_code == 406


def test_export_streaming_pages_large_dataset():
    """Service paginates repository reads and streams JSON without buffering all rows."""
    store = TaxonomyStore()
    skills = SkillRepository(store)
    categories = CategoryRepository(store)
    proficiencies = ProficiencyRepository(store)
    tenant_id = UUID(DEMO_TENANT)

    for i in range(1200):
        skills.create(
            Skill(
                tenant_id=tenant_id,
                version=1,
                code=f"SKILL-{i:04d}",
                name=f"Skill {i}",
            )
        )

    service = TaxonomyExportService(
        skills=skills, categories=categories, proficiencies=proficiencies
    )

    chunks = list(service.stream_json(tenant_id=tenant_id, version=1))
    assert chunks[0].startswith('{"tenant_id":')
    assert chunks[-1] == "]}"
    # Many incremental chunks rather than a single buffered payload.
    assert len(chunks) > 100

    payload = json.loads("".join(chunks))
    assert payload["tenant_id"] == DEMO_TENANT
    assert payload["version"] == 1
    assert len(payload["items"]) == 1200
    assert all(item["entity_type"] == "skill" for item in payload["items"])
    assert all(item["version"] == 1 for item in payload["items"])


def test_resolve_format_accept_quality_list():
    service = TaxonomyExportService(
        skills=SkillRepository(TaxonomyStore()),
        categories=CategoryRepository(TaxonomyStore()),
        proficiencies=ProficiencyRepository(TaxonomyStore()),
    )
    assert (
        service.resolve_format(
            accept="text/csv;q=0.9, application/json;q=0.8",
            format_query=None,
        )
        == "csv"
    )
    assert (
        service.resolve_format(
            accept="application/json, text/csv",
            format_query=None,
        )
        == "json"
    )
