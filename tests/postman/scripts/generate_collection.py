#!/usr/bin/env python3
"""Generate ASIWDP Skills API Postman collection (v2.1)."""

from __future__ import annotations

import json
from pathlib import Path

# Synthetic test IDs only — not real tenant/user data
TENANT_A = "11111111-1111-4111-8111-111111111111"
TENANT_B = "22222222-2222-4222-8222-222222222222"
PLACEHOLDER_SKILL = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
PLACEHOLDER_CAT = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
PLACEHOLDER_PROF = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"

ROOT = Path(__file__).resolve().parents[1]


def header_auth() -> list[dict]:
    return [
        {"key": "Authorization", "value": "Bearer {{access_token}}", "type": "text"},
        {"key": "Accept", "value": "application/json", "type": "text"},
        {"key": "X-Taxonomy-Version", "value": "{{version}}", "type": "text"},
        {"key": "X-Tenant-Id", "value": "{{tenant_id}}", "type": "text"},
    ]


def header_json() -> list[dict]:
    return header_auth() + [
        {"key": "Content-Type", "value": "application/json", "type": "text"}
    ]


def events(test_lines: list[str], prerequest: list[str] | None = None) -> list[dict]:
    ev: list[dict] = []
    if prerequest:
        ev.append(
            {
                "listen": "prerequest",
                "script": {"type": "text/javascript", "exec": prerequest},
            }
        )
    ev.append(
        {"listen": "test", "script": {"type": "text/javascript", "exec": test_lines}}
    )
    return ev


def req(
    name: str,
    method: str,
    path: str,
    *,
    body=None,
    query: list[dict] | None = None,
    headers: list[dict] | None = None,
    tests: list[str] | None = None,
    prerequest: list[str] | None = None,
    description: str = "",
    formdata: list[dict] | None = None,
) -> dict:
    path_parts = [p for p in path.strip("/").split("/") if p]
    raw = "{{baseUrl}}" + path
    url: dict = {
        "raw": raw,
        "host": ["{{baseUrl}}"],
        "path": path_parts,
    }
    if query:
        url["query"] = query
        url["raw"] = raw + "?" + "&".join(f"{q['key']}={q['value']}" for q in query)

    if headers is not None:
        hdrs = headers
    elif formdata is not None:
        hdrs = [h for h in header_auth() if h["key"] != "Content-Type"]
    elif method in ("POST", "PATCH", "PUT"):
        hdrs = header_json()
    else:
        hdrs = header_auth()

    item: dict = {
        "name": name,
        "request": {
            "method": method,
            "header": hdrs,
            "url": url,
            "description": description,
        },
        "response": [],
    }
    if body is not None:
        raw_body = body if isinstance(body, str) else json.dumps(body, indent=2)
        item["request"]["body"] = {
            "mode": "raw",
            "raw": raw_body,
            "options": {"raw": {"language": "json"}},
        }
    if formdata is not None:
        item["request"]["body"] = {"mode": "formdata", "formdata": formdata}
    if tests or prerequest:
        item["event"] = events(tests or [], prerequest)
    return item


SKILL_SCHEMA = [
    "pm.test('Skill schema has required fields', function () {",
    "  const j = pm.response.json();",
    "  pm.expect(j).to.have.keys('id','tenant_id','version','code','name','status');",
    "  pm.expect(j.id).to.match(/^[0-9a-f-]{36}$/i);",
    "  pm.expect(j.tenant_id).to.eql(pm.collectionVariables.get('tenant_id'));",
    "  pm.expect(j.version).to.be.a('number').and.to.be.at.least(1);",
    "  pm.expect(['active','deprecated','draft']).to.include(j.status);",
    "});",
]

ERROR_SCHEMA = [
    "pm.test('Error schema has error and message', function () {",
    "  const j = pm.response.json();",
    "  pm.expect(j).to.have.property('error');",
    "  pm.expect(j).to.have.property('message');",
    "  pm.expect(j.error).to.be.a('string');",
    "  pm.expect(j.message).to.be.a('string');",
    "});",
]

PAGINATED_SKILLS = [
    "pm.test('Paginated skills schema', function () {",
    "  const j = pm.response.json();",
    "  pm.expect(j).to.include.keys('items','total','limit','offset');",
    "  pm.expect(j.items).to.be.an('array');",
    "  pm.expect(j.total).to.be.a('number');",
    "});",
]

IMPORT_REPORT = [
    "pm.test('ImportReport schema', function () {",
    "  const j = pm.response.json();",
    "  const required = ['import_id','tenant_id','version','format','entity_type',"
    "'total_rows','success_count','error_count'];",
    "  required.forEach(k => pm.expect(j, 'missing '+k).to.have.property(k));",
    "  pm.expect(j.tenant_id).to.eql(pm.collectionVariables.get('tenant_id'));",
    "  pm.expect(j.version).to.eql(Number(pm.collectionVariables.get('version')));",
    "});",
]

EXPORT_SCHEMA = [
    "pm.test('TaxonomyExport schema', function () {",
    "  const j = pm.response.json();",
    "  pm.expect(j).to.include.keys('tenant_id','version','items');",
    "  pm.expect(j.items).to.be.an('array');",
    "  pm.expect(j.tenant_id).to.eql(pm.collectionVariables.get('tenant_id'));",
    "});",
]


def status_test(code: int, name: str | None = None) -> list[str]:
    label = name or f"Status code is {code}"
    return [
        f"pm.test('{label}', function () {{",
        f"  pm.response.to.have.status({code});",
        "});",
    ]


def sla_test(ms: int = 50) -> list[str]:
    return [
        f"pm.test('Response time under {ms}ms (SLA)', function () {{",
        f"  pm.expect(pm.response.responseTime).to.be.below({ms});",
        "});",
    ]


def build_collection() -> dict:
    health = {
        "name": "01 Health",
        "description": "Unauthenticated liveness probe",
        "item": [
            req(
                "GET /health — liveness",
                "GET",
                "/health",
                headers=[{"key": "Accept", "value": "application/json"}],
                tests=status_test(200)
                + [
                    "pm.test('Health body status ok', function () {",
                    "  const j = pm.response.json();",
                    "  pm.expect(j).to.have.property('status');",
                    "});",
                ]
                + sla_test(50),
                description="Service liveness; no auth required.",
            )
        ],
    }

    skills_crud = {
        "name": "02 Skills CRUD (valid)",
        "description": (
            "Happy-path create/read/update/retire with {{tenant_id}} "
            "and {{version}} substitution."
        ),
        "item": [
            req(
                "POST /skills — create valid skill",
                "POST",
                "/skills",
                body={
                    "code": "SKILL-{{run_id}}-PY",
                    "name": "Python Programming",
                    "description": "Write and maintain Python applications",
                    "category": "Technical",
                    "tenant_id": "{{tenant_id}}",
                    "version": "{{version}}",
                },
                tests=status_test(201)
                + SKILL_SCHEMA
                + sla_test(50)
                + [
                    "pm.test('Persist skill_id for chained requests', function () {",
                    "  const j = pm.response.json();",
                    "  pm.collectionVariables.set('skill_id', j.id);",
                    "  pm.expect(String(j.version)).to.eql("
                    "String(pm.collectionVariables.get('version')));",
                    "});",
                ],
                description=(
                    "Create skill; captures skill_id. Uses {{tenant_id}} and {{version}}."
                ),
            ),
            req(
                "GET /skills — list by tenant/version",
                "GET",
                "/skills",
                query=[
                    {"key": "version", "value": "{{version}}"},
                    {"key": "status", "value": "active"},
                    {"key": "limit", "value": "50"},
                    {"key": "offset", "value": "0"},
                ],
                tests=status_test(200)
                + PAGINATED_SKILLS
                + sla_test(50)
                + [
                    "pm.test('Listed items match tenant_id', function () {",
                    "  const j = pm.response.json();",
                    "  const tid = pm.collectionVariables.get('tenant_id');",
                    "  j.items.forEach(s => pm.expect(s.tenant_id).to.eql(tid));",
                    "});",
                ],
            ),
            req(
                "GET /skills/{skillId} — get by id",
                "GET",
                "/skills/{{skill_id}}",
                tests=status_test(200) + SKILL_SCHEMA + sla_test(50),
            ),
            req(
                "PATCH /skills/{skillId} — update valid",
                "PATCH",
                "/skills/{{skill_id}}",
                body={
                    "name": "Python Programming (Advanced)",
                    "description": "Updated description",
                    "category": "Technical",
                },
                tests=status_test(200)
                + SKILL_SCHEMA
                + [
                    "pm.test('Name was updated', function () {",
                    "  pm.expect(pm.response.json().name).to.include('Advanced');",
                    "});",
                ]
                + sla_test(50),
            ),
            req(
                "GET /skills/search — search by name",
                "GET",
                "/skills/search",
                query=[
                    {"key": "q", "value": "Python"},
                    {"key": "version", "value": "{{version}}"},
                    {"key": "limit", "value": "25"},
                    {"key": "offset", "value": "0"},
                ],
                tests=status_test(200) + PAGINATED_SKILLS + sla_test(50),
            ),
            req(
                "POST /skills/{skillId}/retire — retire skill",
                "POST",
                "/skills/{{skill_id}}/retire",
                body={},
                tests=status_test(200)
                + SKILL_SCHEMA
                + [
                    "pm.test('Status is deprecated', function () {",
                    "  pm.expect(pm.response.json().status).to.eql('deprecated');",
                    "});",
                ]
                + sla_test(50),
            ),
        ],
    }

    skills_malformed = {
        "name": "03 Skills CRUD (malformed)",
        "description": (
            "Negative validation cases — missing fields, wrong types, empty body."
        ),
        "item": [
            req(
                "POST /skills — missing required code/name",
                "POST",
                "/skills",
                body={
                    "description": "no code or name",
                    "tenant_id": "{{tenant_id}}",
                    "version": "{{version}}",
                },
                tests=status_test(400) + ERROR_SCHEMA,
            ),
            req(
                "POST /skills — empty body",
                "POST",
                "/skills",
                body={},
                tests=status_test(400) + ERROR_SCHEMA,
            ),
            req(
                "POST /skills — invalid parent_skill_id type",
                "POST",
                "/skills",
                body={
                    "code": "BAD-PARENT",
                    "name": "Bad Parent",
                    "parent_skill_id": "not-a-uuid",
                    "tenant_id": "{{tenant_id}}",
                    "version": "{{version}}",
                },
                tests=status_test(400) + ERROR_SCHEMA,
            ),
            req(
                "POST /skills — version below minimum",
                "POST",
                "/skills",
                body={
                    "code": "BAD-VER",
                    "name": "Bad Version",
                    "tenant_id": "{{tenant_id}}",
                    "version": 0,
                },
                tests=status_test(400) + ERROR_SCHEMA,
            ),
            req(
                "POST /skills — unknown additional property",
                "POST",
                "/skills",
                body={
                    "code": "EXTRA-PROP",
                    "name": "Extra Prop",
                    "not_a_field": True,
                    "tenant_id": "{{tenant_id}}",
                    "version": "{{version}}",
                },
                tests=status_test(400) + ERROR_SCHEMA,
            ),
            req(
                "PATCH /skills/{skillId} — invalid status enum",
                "PATCH",
                "/skills/{{skill_id}}",
                body={"status": "archived"},
                tests=status_test(400) + ERROR_SCHEMA,
            ),
            req(
                "GET /skills/{skillId} — unknown id returns 404",
                "GET",
                f"/skills/{PLACEHOLDER_SKILL}",
                tests=status_test(404) + ERROR_SCHEMA,
            ),
            req(
                "GET /skills — unauthorized without token",
                "GET",
                "/skills",
                headers=[
                    {"key": "Accept", "value": "application/json"},
                    {"key": "X-Taxonomy-Version", "value": "{{version}}"},
                ],
                query=[{"key": "version", "value": "{{version}}"}],
                tests=status_test(401) + ERROR_SCHEMA,
            ),
        ],
    }

    categories = {
        "name": "04 Categories CRUD",
        "item": [
            req(
                "POST /categories — create valid",
                "POST",
                "/categories",
                body={
                    "code": "CAT-{{run_id}}-TECH",
                    "name": "Technical Skills",
                    "description": "Engineering and IT",
                    "tenant_id": "{{tenant_id}}",
                    "version": "{{version}}",
                },
                tests=status_test(201)
                + [
                    "pm.test('Category schema', function () {",
                    "  const j = pm.response.json();",
                    "  pm.expect(j).to.include.keys("
                    "'id','tenant_id','version','code','name','status');",
                    "  pm.collectionVariables.set('category_id', j.id);",
                    "});",
                ]
                + sla_test(50),
            ),
            req(
                "GET /categories/{categoryId}",
                "GET",
                "/categories/{{category_id}}",
                tests=status_test(200)
                + [
                    "pm.test('Category tenant matches', function () {",
                    "  pm.expect(pm.response.json().tenant_id)"
                    ".to.eql(pm.collectionVariables.get('tenant_id'));",
                    "});",
                ],
            ),
            req(
                "PATCH /categories/{categoryId}",
                "PATCH",
                "/categories/{{category_id}}",
                body={"name": "Technical Skills (Updated)"},
                tests=status_test(200),
            ),
            req(
                "POST /categories — malformed missing name",
                "POST",
                "/categories",
                body={
                    "code": "CAT-BAD",
                    "tenant_id": "{{tenant_id}}",
                    "version": "{{version}}",
                },
                tests=status_test(400) + ERROR_SCHEMA,
            ),
            req(
                "POST /categories/{categoryId}/retire",
                "POST",
                "/categories/{{category_id}}/retire",
                body={},
                tests=status_test(200)
                + [
                    "pm.test('Category deprecated', function () {",
                    "  pm.expect(pm.response.json().status).to.eql('deprecated');",
                    "});",
                ],
            ),
        ],
    }

    proficiencies = {
        "name": "05 Proficiencies CRUD",
        "item": [
            req(
                "POST /proficiencies — create valid",
                "POST",
                "/proficiencies",
                body={
                    "level": 3,
                    "code": "PROF-{{run_id}}-L3",
                    "name": "Proficient",
                    "rank_order": 30,
                    "description": "Works independently",
                    "tenant_id": "{{tenant_id}}",
                    "version": "{{version}}",
                },
                tests=status_test(201)
                + [
                    "pm.test('Proficiency schema', function () {",
                    "  const j = pm.response.json();",
                    "  pm.expect(j).to.include.keys("
                    "'id','tenant_id','version','level','code','name','rank_order','status');",
                    "  pm.collectionVariables.set('proficiency_id', j.id);",
                    "});",
                ]
                + sla_test(50),
            ),
            req(
                "GET /proficiencies/{proficiencyId}",
                "GET",
                "/proficiencies/{{proficiency_id}}",
                tests=status_test(200),
            ),
            req(
                "PATCH /proficiencies/{proficiencyId}",
                "PATCH",
                "/proficiencies/{{proficiency_id}}",
                body={"name": "Proficient+", "rank_order": 35},
                tests=status_test(200),
            ),
            req(
                "POST /proficiencies — malformed level < 1",
                "POST",
                "/proficiencies",
                body={
                    "level": 0,
                    "code": "PROF-BAD",
                    "name": "Invalid",
                    "rank_order": 1,
                    "tenant_id": "{{tenant_id}}",
                    "version": "{{version}}",
                },
                tests=status_test(400) + ERROR_SCHEMA,
            ),
            req(
                "POST /proficiencies/{proficiencyId}/retire",
                "POST",
                "/proficiencies/{{proficiency_id}}/retire",
                body={},
                tests=status_test(200)
                + [
                    "pm.test('Proficiency deprecated', function () {",
                    "  pm.expect(pm.response.json().status).to.eql('deprecated');",
                    "});",
                ],
            ),
        ],
    }

    bulk_import = {
        "name": "06 Bulk Import",
        "description": "POST /taxonomy/import — valid CSV/JSON and malformed rows.",
        "item": [
            req(
                "POST /taxonomy/import — valid JSON skills",
                "POST",
                "/taxonomy/import",
                formdata=[
                    {"key": "entity_type", "value": "skill", "type": "text"},
                    {"key": "format", "value": "json", "type": "text"},
                    {"key": "version", "value": "{{version}}", "type": "text"},
                    {
                        "key": "file",
                        "type": "file",
                        "src": "fixtures/skills-import-valid.json",
                    },
                ],
                tests=status_test(200)
                + IMPORT_REPORT
                + [
                    "pm.test('All rows succeeded', function () {",
                    "  const j = pm.response.json();",
                    "  pm.expect(j.error_count).to.eql(0);",
                    "  pm.expect(j.success_count).to.be.at.least(1);",
                    "  pm.expect(j.entity_type).to.eql('skill');",
                    "});",
                ],
                description=(
                    "Bulk import valid JSON skills; tenant comes from JWT "
                    "({{tenant_id}}); version from form {{version}}."
                ),
            ),
            req(
                "POST /taxonomy/import — valid CSV skills",
                "POST",
                "/taxonomy/import",
                formdata=[
                    {"key": "entity_type", "value": "skill", "type": "text"},
                    {"key": "format", "value": "csv", "type": "text"},
                    {"key": "version", "value": "{{version}}", "type": "text"},
                    {
                        "key": "file",
                        "type": "file",
                        "src": "fixtures/skills-import-valid.csv",
                    },
                ],
                tests=status_test(200)
                + IMPORT_REPORT
                + [
                    "pm.test('CSV import success_count > 0', function () {",
                    "  pm.expect(pm.response.json().success_count).to.be.above(0);",
                    "});",
                ],
            ),
            req(
                "POST /taxonomy/import — malformed rows (partial failure report)",
                "POST",
                "/taxonomy/import",
                formdata=[
                    {"key": "entity_type", "value": "skill", "type": "text"},
                    {"key": "format", "value": "json", "type": "text"},
                    {"key": "version", "value": "{{version}}", "type": "text"},
                    {
                        "key": "file",
                        "type": "file",
                        "src": "fixtures/skills-import-malformed.json",
                    },
                ],
                tests=status_test(200)
                + IMPORT_REPORT
                + [
                    "pm.test('Row-level errors present', function () {",
                    "  const j = pm.response.json();",
                    "  pm.expect(j.error_count).to.be.at.least(1);",
                    "  pm.expect(j.errors).to.be.an('array').and.not.empty;",
                    "  pm.expect(j.errors[0]).to.have.property('row_number');",
                    "  pm.expect(j.errors[0]).to.have.property('errors');",
                    "});",
                ],
                description=(
                    "Expect ImportReport with per-row validation errors for "
                    "missing code/name and bad version."
                ),
            ),
            req(
                "POST /taxonomy/import — missing file (400)",
                "POST",
                "/taxonomy/import",
                formdata=[
                    {"key": "entity_type", "value": "skill", "type": "text"},
                    {"key": "format", "value": "json", "type": "text"},
                    {"key": "version", "value": "{{version}}", "type": "text"},
                ],
                tests=status_test(400) + ERROR_SCHEMA,
            ),
            req(
                "POST /taxonomy/import — invalid entity_type",
                "POST",
                "/taxonomy/import",
                formdata=[
                    {"key": "entity_type", "value": "role", "type": "text"},
                    {"key": "format", "value": "json", "type": "text"},
                    {"key": "version", "value": "{{version}}", "type": "text"},
                    {
                        "key": "file",
                        "type": "file",
                        "src": "fixtures/skills-import-valid.json",
                    },
                ],
                tests=status_test(400) + ERROR_SCHEMA,
            ),
            req(
                "POST /taxonomy/import — version mismatch (malformed version=0)",
                "POST",
                "/taxonomy/import",
                formdata=[
                    {"key": "entity_type", "value": "skill", "type": "text"},
                    {"key": "format", "value": "json", "type": "text"},
                    {"key": "version", "value": "0", "type": "text"},
                    {
                        "key": "file",
                        "type": "file",
                        "src": "fixtures/skills-import-valid.json",
                    },
                ],
                tests=status_test(400) + ERROR_SCHEMA,
            ),
        ],
    }

    bulk_export = {
        "name": "07 Bulk Export",
        "description": (
            "GET /taxonomy/export — JSON/CSV with tenant_id and version filters."
        ),
        "item": [
            req(
                "GET /taxonomy/export — JSON current version",
                "GET",
                "/taxonomy/export",
                query=[
                    {"key": "tenant_id", "value": "{{tenant_id}}"},
                    {"key": "version", "value": "{{version}}"},
                    {"key": "format", "value": "json"},
                ],
                tests=status_test(200)
                + EXPORT_SCHEMA
                + sla_test(50)
                + [
                    "pm.test('Export version matches request', function () {",
                    "  const j = pm.response.json();",
                    "  pm.expect(Number(j.version)).to.eql("
                    "Number(pm.collectionVariables.get('version')));",
                    "});",
                ],
            ),
            req(
                "GET /taxonomy/export — CSV format",
                "GET",
                "/taxonomy/export",
                headers=[
                    {
                        "key": "Authorization",
                        "value": "Bearer {{access_token}}",
                        "type": "text",
                    },
                    {"key": "Accept", "value": "text/csv", "type": "text"},
                    {
                        "key": "X-Taxonomy-Version",
                        "value": "{{version}}",
                        "type": "text",
                    },
                    {"key": "X-Tenant-Id", "value": "{{tenant_id}}", "type": "text"},
                ],
                query=[
                    {"key": "tenant_id", "value": "{{tenant_id}}"},
                    {"key": "version", "value": "{{version}}"},
                    {"key": "format", "value": "csv"},
                ],
                tests=status_test(200)
                + [
                    "pm.test('CSV content-type', function () {",
                    "  const ct = pm.response.headers.get('Content-Type') || '';",
                    "  pm.expect(ct).to.match(/text\\/csv|application\\/octet-stream/i);",
                    "});",
                    "pm.test('CSV has header row', function () {",
                    "  const text = pm.response.text();",
                    "  pm.expect(text.split('\\n')[0].toLowerCase())"
                    ".to.match(/code|name|tenant/);",
                    "});",
                ],
            ),
            req(
                "GET /taxonomy/export — historic version snapshot",
                "GET",
                "/taxonomy/export",
                query=[
                    {"key": "tenant_id", "value": "{{tenant_id}}"},
                    {"key": "version", "value": "{{historic_version}}"},
                    {"key": "format", "value": "json"},
                ],
                tests=status_test(200)
                + EXPORT_SCHEMA
                + [
                    "pm.test('Historic version echoed', function () {",
                    "  pm.expect(Number(pm.response.json().version)).to.eql("
                    "Number(pm.collectionVariables.get('historic_version')));",
                    "});",
                ],
            ),
            req(
                "GET /taxonomy/export — mismatched tenant_id forbidden",
                "GET",
                "/taxonomy/export",
                query=[
                    {"key": "tenant_id", "value": TENANT_B},
                    {"key": "version", "value": "{{version}}"},
                    {"key": "format", "value": "json"},
                ],
                tests=status_test(403) + ERROR_SCHEMA,
                description=(
                    "Caller JWT tenant must match query tenant_id; "
                    "expect 403 for foreign tenant."
                ),
            ),
            req(
                "GET /taxonomy/export — unsupported format (406)",
                "GET",
                "/taxonomy/export",
                query=[
                    {"key": "tenant_id", "value": "{{tenant_id}}"},
                    {"key": "version", "value": "{{version}}"},
                    {"key": "format", "value": "xml"},
                ],
                tests=[
                    "pm.test('Status is 406 or 400 for unsupported format', function () {",
                    "  pm.expect([400, 406]).to.include(pm.response.code);",
                    "});",
                ]
                + ERROR_SCHEMA,
            ),
        ],
    }

    versioning = {
        "name": "08 Versioning Scenarios",
        "description": (
            "X-Taxonomy-Version header and version query isolation across "
            "taxonomy revisions."
        ),
        "item": [
            req(
                "POST /skills — create on version {{version}}",
                "POST",
                "/skills",
                body={
                    "code": "VER-{{run_id}}-V1",
                    "name": "Versioned Skill v-current",
                    "tenant_id": "{{tenant_id}}",
                    "version": "{{version}}",
                },
                tests=status_test(201)
                + SKILL_SCHEMA
                + [
                    "pm.test('Stored version equals {{version}}', function () {",
                    "  pm.expect(Number(pm.response.json().version)).to.eql("
                    "Number(pm.collectionVariables.get('version')));",
                    "  pm.collectionVariables.set('versioned_skill_id', "
                    "pm.response.json().id);",
                    "});",
                ],
            ),
            req(
                "POST /skills — create on historic_version",
                "POST",
                "/skills",
                headers=[
                    {
                        "key": "Authorization",
                        "value": "Bearer {{access_token}}",
                        "type": "text",
                    },
                    {"key": "Accept", "value": "application/json", "type": "text"},
                    {
                        "key": "Content-Type",
                        "value": "application/json",
                        "type": "text",
                    },
                    {
                        "key": "X-Taxonomy-Version",
                        "value": "{{historic_version}}",
                        "type": "text",
                    },
                    {"key": "X-Tenant-Id", "value": "{{tenant_id}}", "type": "text"},
                ],
                body={
                    "code": "VER-{{run_id}}-VH",
                    "name": "Versioned Skill historic",
                    "tenant_id": "{{tenant_id}}",
                    "version": "{{historic_version}}",
                },
                tests=status_test(201)
                + [
                    "pm.test('Historic version persisted', function () {",
                    "  pm.expect(Number(pm.response.json().version)).to.eql("
                    "Number(pm.collectionVariables.get('historic_version')));",
                    "});",
                ],
            ),
            req(
                "GET /skills — filter version={{version}}",
                "GET",
                "/skills",
                query=[
                    {"key": "version", "value": "{{version}}"},
                    {"key": "limit", "value": "100"},
                    {"key": "offset", "value": "0"},
                ],
                tests=status_test(200)
                + PAGINATED_SKILLS
                + [
                    "pm.test('All items are current version', function () {",
                    "  const v = Number(pm.collectionVariables.get('version'));",
                    "  pm.response.json().items.forEach("
                    "s => pm.expect(s.version).to.eql(v));",
                    "});",
                ],
            ),
            req(
                "GET /skills — filter version={{historic_version}}",
                "GET",
                "/skills",
                headers=[
                    {
                        "key": "Authorization",
                        "value": "Bearer {{access_token}}",
                        "type": "text",
                    },
                    {"key": "Accept", "value": "application/json", "type": "text"},
                    {
                        "key": "X-Taxonomy-Version",
                        "value": "{{historic_version}}",
                        "type": "text",
                    },
                    {"key": "X-Tenant-Id", "value": "{{tenant_id}}", "type": "text"},
                ],
                query=[
                    {"key": "version", "value": "{{historic_version}}"},
                    {"key": "limit", "value": "100"},
                    {"key": "offset", "value": "0"},
                ],
                tests=status_test(200)
                + PAGINATED_SKILLS
                + [
                    "pm.test('All items are historic version', function () {",
                    "  const v = Number(pm.collectionVariables.get('historic_version'));",
                    "  pm.response.json().items.forEach("
                    "s => pm.expect(s.version).to.eql(v));",
                    "});",
                ],
            ),
            req(
                "GET /skills/search — version-scoped search",
                "GET",
                "/skills/search",
                query=[
                    {"key": "q", "value": "Versioned"},
                    {"key": "version", "value": "{{version}}"},
                    {"key": "limit", "value": "50"},
                    {"key": "offset", "value": "0"},
                ],
                tests=status_test(200)
                + PAGINATED_SKILLS
                + [
                    "pm.test('Search results stay on requested version', function () {",
                    "  const v = Number(pm.collectionVariables.get('version'));",
                    "  pm.response.json().items.forEach("
                    "s => pm.expect(s.version).to.eql(v));",
                    "});",
                ],
            ),
            req(
                "GET /taxonomy/export — version={{version}} snapshot",
                "GET",
                "/taxonomy/export",
                query=[
                    {"key": "tenant_id", "value": "{{tenant_id}}"},
                    {"key": "version", "value": "{{version}}"},
                    {"key": "format", "value": "json"},
                ],
                tests=status_test(200)
                + EXPORT_SCHEMA
                + [
                    "pm.test('Capture current export count', function () {",
                    "  pm.collectionVariables.set('export_count_current', "
                    "String(pm.response.json().items.length));",
                    "});",
                ],
            ),
        ],
    }

    tenant_isolation = {
        "name": "09 Tenant Isolation",
        "description": (
            "Ensure {{tenant_id}} scoping; foreign tenant data is not readable."
        ),
        "item": [
            req(
                "GET /skills — list only returns caller's tenant",
                "GET",
                "/skills",
                query=[
                    {"key": "version", "value": "{{version}}"},
                    {"key": "limit", "value": "100"},
                    {"key": "offset", "value": "0"},
                ],
                tests=status_test(200)
                + PAGINATED_SKILLS
                + [
                    "pm.test('No foreign tenant_id in list', function () {",
                    "  const tid = pm.collectionVariables.get('tenant_id');",
                    "  pm.response.json().items.forEach(s => {",
                    "    pm.expect(s.tenant_id).to.eql(tid);",
                    f"    pm.expect(s.tenant_id).to.not.eql('{TENANT_B}');",
                    "  });",
                    "});",
                ],
            ),
            req(
                "POST /skills — body tenant_id ignored/overridden by JWT",
                "POST",
                "/skills",
                body={
                    "code": "ISO-{{run_id}}-X",
                    "name": "Isolation Probe",
                    "tenant_id": TENANT_B,
                    "version": "{{version}}",
                },
                tests=status_test(201)
                + [
                    "pm.test('Persisted tenant is JWT tenant not body tenant', "
                    "function () {",
                    "  const j = pm.response.json();",
                    "  pm.expect(j.tenant_id).to.eql("
                    "pm.collectionVariables.get('tenant_id'));",
                    f"  pm.expect(j.tenant_id).to.not.eql('{TENANT_B}');",
                    "});",
                ],
            ),
        ],
    }

    return {
        "info": {
            "_postman_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "name": "ASIWDP Skills Framework API",
            "description": (
                "Automated API test suite for the ASIWDP Skills Framework & "
                "Competency Management Service.\n\n"
                "Covers CRUD, bulk import/export, taxonomy versioning, tenant "
                "isolation, and malformed payloads.\n\n"
                "**Variables:** `baseUrl`, `tenant_id`, `version`, "
                "`historic_version`, `access_token`, `skill_id`, `category_id`, "
                "`proficiency_id`.\n\n"
                "Aligned with OpenAPI skills-framework-service.yaml "
                "(versioned CRUD + /taxonomy/import|export).\n\n"
                "Story: Automated API Test Suites for Skills Service "
                "(QA — Maya Silva).\n"
                "Project: AI-Powered Skills Intelligence & Workforce Development "
                "Platform (ASIWDP)."
            ),
            "schema": (
                "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
            ),
        },
        "auth": {
            "type": "bearer",
            "bearer": [
                {"key": "token", "value": "{{access_token}}", "type": "string"}
            ],
        },
        "variable": [
            {"key": "baseUrl", "value": "http://localhost:8080/api/v1"},
            {"key": "tenant_id", "value": TENANT_A},
            {"key": "version", "value": "1"},
            {"key": "historic_version", "value": "1"},
            {"key": "access_token", "value": ""},
            {"key": "skill_id", "value": PLACEHOLDER_SKILL},
            {"key": "category_id", "value": PLACEHOLDER_CAT},
            {"key": "proficiency_id", "value": PLACEHOLDER_PROF},
            {"key": "run_id", "value": ""},
            {"key": "versioned_skill_id", "value": ""},
            {"key": "export_count_current", "value": "0"},
        ],
        "event": [
            {
                "listen": "prerequest",
                "script": {
                    "type": "text/javascript",
                    "exec": [
                        "// Collection pre-request: ensure run_id for unique codes",
                        "if (!pm.collectionVariables.get('run_id')) {",
                        "  pm.collectionVariables.set('run_id', Date.now().toString(36));",
                        "}",
                    ],
                },
            },
            {
                "listen": "test",
                "script": {
                    "type": "text/javascript",
                    "exec": [
                        "// Collection-level: always record response for CI reports",
                        "pm.test('Response received', function () {",
                        "  pm.expect(pm.response.code).to.be.a('number');",
                        "});",
                    ],
                },
            },
        ],
        "item": [
            health,
            skills_crud,
            skills_malformed,
            categories,
            proficiencies,
            bulk_import,
            bulk_export,
            versioning,
            tenant_isolation,
        ],
    }


def build_environment() -> dict:
    return {
        "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
        "name": "ASIWDP Skills API — Local",
        "values": [
            {
                "key": "baseUrl",
                "value": "http://localhost:8080/api/v1",
                "enabled": True,
                "type": "default",
            },
            {
                "key": "tenant_id",
                "value": TENANT_A,
                "enabled": True,
                "type": "default",
            },
            {"key": "version", "value": "1", "enabled": True, "type": "default"},
            {
                "key": "historic_version",
                "value": "1",
                "enabled": True,
                "type": "default",
            },
            {
                "key": "access_token",
                "value": "",
                "enabled": True,
                "type": "secret",
            },
            {"key": "skill_id", "value": "", "enabled": True, "type": "default"},
            {"key": "category_id", "value": "", "enabled": True, "type": "default"},
            {
                "key": "proficiency_id",
                "value": "",
                "enabled": True,
                "type": "default",
            },
        ],
        "_postman_variable_scope": "environment",
    }


def main() -> None:
    collection = build_collection()
    env = build_environment()

    out_collection = ROOT / "skills-api-collection.json"
    out_env = ROOT / "skills-api.environment.json"

    out_collection.write_text(json.dumps(collection, indent=2) + "\n", encoding="utf-8")
    out_env.write_text(json.dumps(env, indent=2) + "\n", encoding="utf-8")

    request_count = sum(len(folder["item"]) for folder in collection["item"])
    print(f"Wrote {out_collection} ({len(collection['item'])} folders, {request_count} requests)")
    print(f"Wrote {out_env}")


if __name__ == "__main__":
    main()
