"""API tests for version-aware CRUD and taxonomy export."""

from __future__ import annotations

import io
import json
from uuid import UUID

DEMO_TENANT = "22222222-2222-2222-2222-222222222222"


def test_skill_crud_list_search_retire(client, tenant_headers):
    create = client.post(
        "/api/v1/skills",
        headers=tenant_headers,
        json={
            "code": "python",
            "name": "Python Programming",
            "description": "Write Python",
            "category": "Technical",
            "version": 1,
        },
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["code"] == "PYTHON"
    assert body["version"] == 1
    assert body["tenant_id"] == DEMO_TENANT
    skill_id = body["id"]

    got = client.get(f"/api/v1/skills/{skill_id}", headers=tenant_headers)
    assert got.status_code == 200
    assert got.json()["name"] == "Python Programming"

    updated = client.patch(
        f"/api/v1/skills/{skill_id}",
        headers=tenant_headers,
        json={"name": "Python 3"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Python 3"
    assert updated.json()["version"] == 1

    listed = client.get("/api/v1/skills", headers=tenant_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    searched = client.get(
        "/api/v1/skills/search", headers=tenant_headers, params={"q": "python"}
    )
    assert searched.status_code == 200
    assert searched.json()["total"] == 1

    retired = client.post(
        f"/api/v1/skills/{skill_id}/retire", headers=tenant_headers
    )
    assert retired.status_code == 200
    assert retired.json()["status"] == "deprecated"


def test_category_and_proficiency_crud(client, tenant_headers):
    cat = client.post(
        "/api/v1/categories",
        headers=tenant_headers,
        json={"code": "TECHNICAL", "name": "Technical"},
    )
    assert cat.status_code == 201
    assert cat.json()["version"] == 1

    prof = client.post(
        "/api/v1/proficiencies",
        headers=tenant_headers,
        json={
            "level": 1,
            "code": "AWARE",
            "name": "Awareness",
            "rank_order": 1,
        },
    )
    assert prof.status_code == 201
    assert prof.json()["version"] == 1

    cat_search = client.get(
        "/api/v1/categories/search",
        headers=tenant_headers,
        params={"q": "tech"},
    )
    assert cat_search.json()["total"] == 1

    retired = client.post(
        f"/api/v1/proficiencies/{prof.json()['id']}/retire",
        headers=tenant_headers,
    )
    assert retired.json()["status"] == "deprecated"


def test_import_endpoint_returns_report(client, tenant_headers):
    csv_body = (
        "tenant_id,version,code,name,category\n"
        f"{DEMO_TENANT},1,DATA-LIT,Data Literacy,Foundational\n"
        f"{DEMO_TENANT},1,,Bad Row\n"
    )
    response = client.post(
        "/api/v1/taxonomy/import",
        headers=tenant_headers,
        data={"entity_type": "skill", "format": "csv", "version": "1"},
        files={"file": ("skills.csv", io.BytesIO(csv_body.encode()), "text/csv")},
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["success_count"] == 1
    assert report["error_count"] == 1
    assert report["audit_entries"] == 1
    assert report["version"] == 1


def test_export_json_and_csv_streaming(client, tenant_headers):
    client.post(
        "/api/v1/skills",
        headers=tenant_headers,
        json={"code": "SQL", "name": "SQL", "category": "Technical"},
    )
    client.post(
        "/api/v1/categories",
        headers=tenant_headers,
        json={"code": "TECHNICAL", "name": "Technical"},
    )
    client.post(
        "/api/v1/proficiencies",
        headers=tenant_headers,
        json={"level": 1, "code": "AWARE", "name": "Awareness", "rank_order": 1},
    )

    json_resp = client.get(
        "/api/v1/taxonomy/export",
        headers={**tenant_headers, "Accept": "application/json"},
        params={"tenant_id": DEMO_TENANT, "version": 1},
    )
    assert json_resp.status_code == 200
    assert json_resp.headers["content-type"].startswith("application/json")
    payload = json_resp.json()
    assert payload["tenant_id"] == DEMO_TENANT
    assert payload["version"] == 1
    assert len(payload["items"]) == 3

    csv_resp = client.get(
        "/api/v1/taxonomy/export",
        headers={**tenant_headers, "Accept": "text/csv"},
        params={"version": 1},
    )
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["content-type"]
    lines = csv_resp.text.strip().splitlines()
    assert lines[0].startswith("entity_type,")
    assert len(lines) == 4  # header + 3 rows


def test_export_rejects_cross_tenant(client, tenant_headers):
    other = "11111111-1111-1111-1111-111111111111"
    resp = client.get(
        "/api/v1/taxonomy/export",
        headers=tenant_headers,
        params={"tenant_id": other},
    )
    assert resp.status_code == 403


def test_version_header_persisted(client, tenant_headers):
    headers = {**tenant_headers, "X-Taxonomy-Version": "2"}
    created = client.post(
        "/api/v1/skills",
        headers=headers,
        json={"code": "ML", "name": "Machine Learning"},
    )
    assert created.status_code == 201
    assert created.json()["version"] == 2
