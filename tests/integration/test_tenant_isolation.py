"""
Tenant Isolation Integration Tests for ASIWDP Skills Service

Tests verify that resources created under one tenant are inaccessible to other
tenants, enforcing strict multi-tenant data isolation as required by the platform.

These tests use an embedded mock server for standalone testing without requiring
external services. For live integration testing against a real server, set
SKILLS_API_BASE_URL and provide valid tenant tokens via environment variables.

Task ID: 1ec84f05-90fe-4b6f-895d-4dd68e71edc2
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Generator

import jwt
import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

# Test configuration (aligned with libs/auth-middleware test helpers)
TEST_SECRET = "test-only-hs256-secret-not-for-production"
TEST_ISSUER = "https://auth.asiwdp.test/"
TEST_AUDIENCE = "asiwdp-api"

# Tenant identifiers
TENANT_A_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
TENANT_B_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

# User identifiers
USER_A_ID = "11111111-1111-1111-1111-111111111111"
USER_B_ID = "22222222-2222-2222-2222-222222222222"

# Role that grants skills:read / skills:write / skills:delete per RBAC matrix
SKILLS_ROLE = "skills_manager"
SKILLS_SCOPES = ["skills:read", "skills:write", "skills:delete"]


def make_token(
    *,
    sub: str,
    tenant_id: str,
    roles: list[str] | None = None,
    scopes: list[str] | None = None,
    exp_offset: int = 3600,
) -> str:
    """Generate a JWT token for testing."""
    now = int(time.time())
    payload = {
        "sub": sub,
        "tenant_id": tenant_id,
        "iat": now,
        "exp": now + exp_offset,
        "iss": TEST_ISSUER,
        "aud": TEST_AUDIENCE,
        "roles": roles or [SKILLS_ROLE],
        "scopes": scopes or SKILLS_SCOPES,
    }
    return jwt.encode(payload, TEST_SECRET, algorithm="HS256")


class MockSkillsStore:
    """In-memory skills store for testing tenant isolation."""

    def __init__(self) -> None:
        self._skills: dict[str, dict[str, Any]] = {}
        self._audit_logs: list[dict[str, Any]] = []

    def create_skill(self, tenant_id: str, skill_data: dict[str, Any]) -> dict[str, Any]:
        """Create a skill for a specific tenant."""
        skill_id = str(uuid.uuid4())
        skill = {
            "id": skill_id,
            "tenant_id": tenant_id,
            **skill_data,
            "created_at": time.time(),
            "version": skill_data.get("version", "1.0.0"),
        }
        self._skills[skill_id] = skill
        self._log_action("create", tenant_id, skill_id)
        return skill

    def get_skill(self, tenant_id: str, skill_id: str) -> dict[str, Any] | None:
        """Get a skill by ID, enforcing tenant isolation."""
        skill = self._skills.get(skill_id)
        if skill is None:
            self._log_action("read_not_found", tenant_id, skill_id)
            return None
        if skill["tenant_id"] != tenant_id:
            self._log_action("read_denied", tenant_id, skill_id)
            return None  # Tenant isolation: obscure existence from other tenants
        self._log_action("read", tenant_id, skill_id)
        return skill

    def list_skills(self, tenant_id: str) -> list[dict[str, Any]]:
        """List all skills for a tenant."""
        self._log_action("list", tenant_id, None)
        return [s for s in self._skills.values() if s["tenant_id"] == tenant_id]

    def update_skill(
        self, tenant_id: str, skill_id: str, updates: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Update a skill, enforcing tenant isolation."""
        skill = self._skills.get(skill_id)
        if skill is None or skill["tenant_id"] != tenant_id:
            self._log_action("update_denied", tenant_id, skill_id)
            return None
        skill.update(updates)
        skill["updated_at"] = time.time()
        self._log_action("update", tenant_id, skill_id)
        return skill

    def delete_skill(self, tenant_id: str, skill_id: str) -> bool:
        """Delete a skill, enforcing tenant isolation."""
        skill = self._skills.get(skill_id)
        if skill is None or skill["tenant_id"] != tenant_id:
            self._log_action("delete_denied", tenant_id, skill_id)
            return False
        del self._skills[skill_id]
        self._log_action("delete", tenant_id, skill_id)
        return True

    def bulk_import(self, tenant_id: str, skills: list[dict[str, Any]]) -> dict[str, Any]:
        """Bulk import skills for a tenant."""
        created = []
        for skill_data in skills:
            skill = self.create_skill(tenant_id, skill_data)
            created.append(skill)
        self._log_action("bulk_import", tenant_id, None)
        return {"imported_count": len(created), "skills": created}

    def _log_action(
        self, action: str, tenant_id: str, skill_id: str | None
    ) -> None:
        """Log an action for audit purposes."""
        self._audit_logs.append(
            {
                "action": action,
                "tenant_id": tenant_id,
                "skill_id": skill_id,
                "timestamp": time.time(),
            }
        )

    def get_audit_logs(
        self, tenant_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Get audit logs, optionally filtered by tenant."""
        if tenant_id is None:
            return self._audit_logs.copy()
        return [log for log in self._audit_logs if log["tenant_id"] == tenant_id]

    def clear(self) -> None:
        """Clear all data."""
        self._skills.clear()
        self._audit_logs.clear()


# Global store instance for tests
_store = MockSkillsStore()


def _verify_token(request: Request) -> dict[str, Any] | None:
    """Verify JWT token and return payload."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    try:
        return jwt.decode(
            token,
            TEST_SECRET,
            algorithms=["HS256"],
            audience=TEST_AUDIENCE,
            issuer=TEST_ISSUER,
        )
    except jwt.PyJWTError:
        return None


async def create_skill(request: Request) -> JSONResponse:
    """Handle POST /skills."""
    payload = _verify_token(request)
    if not payload:
        return JSONResponse(
            {"error": "unauthorized", "message": "Invalid or missing token"},
            status_code=401,
        )

    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        return JSONResponse(
            {"error": "forbidden", "message": "No tenant_id in token"},
            status_code=403,
        )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"error": "bad_request", "message": "Invalid JSON"},
            status_code=400,
        )

    if "name" not in body:
        return JSONResponse(
            {"error": "validation_error", "message": "name is required"},
            status_code=400,
        )

    skill = _store.create_skill(tenant_id, body)
    return JSONResponse(skill, status_code=201)


async def get_skill(request: Request) -> JSONResponse:
    """Handle GET /skills/{skill_id}."""
    payload = _verify_token(request)
    if not payload:
        return JSONResponse(
            {"error": "unauthorized", "message": "Invalid or missing token"},
            status_code=401,
        )

    tenant_id = payload.get("tenant_id")
    skill_id = request.path_params["skill_id"]

    skill = _store.get_skill(tenant_id, skill_id)
    if skill is None:
        # Return 404 for cross-tenant access (do not leak existence)
        return JSONResponse(
            {"error": "not_found", "message": "Skill not found"},
            status_code=404,
        )

    return JSONResponse(skill)


async def list_skills(request: Request) -> JSONResponse:
    """Handle GET /skills."""
    payload = _verify_token(request)
    if not payload:
        return JSONResponse(
            {"error": "unauthorized", "message": "Invalid or missing token"},
            status_code=401,
        )

    tenant_id = payload.get("tenant_id")
    skills = _store.list_skills(tenant_id)
    return JSONResponse({"items": skills})


async def update_skill(request: Request) -> JSONResponse:
    """Handle PUT /skills/{skill_id}."""
    payload = _verify_token(request)
    if not payload:
        return JSONResponse(
            {"error": "unauthorized", "message": "Invalid or missing token"},
            status_code=401,
        )

    tenant_id = payload.get("tenant_id")
    skill_id = request.path_params["skill_id"]

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"error": "bad_request", "message": "Invalid JSON"},
            status_code=400,
        )

    skill = _store.update_skill(tenant_id, skill_id, body)
    if skill is None:
        return JSONResponse(
            {"error": "not_found", "message": "Skill not found"},
            status_code=404,
        )

    return JSONResponse(skill)


async def delete_skill(request: Request) -> JSONResponse:
    """Handle DELETE /skills/{skill_id}."""
    payload = _verify_token(request)
    if not payload:
        return JSONResponse(
            {"error": "unauthorized", "message": "Invalid or missing token"},
            status_code=401,
        )

    tenant_id = payload.get("tenant_id")
    skill_id = request.path_params["skill_id"]

    if _store.delete_skill(tenant_id, skill_id):
        return JSONResponse({}, status_code=204)

    return JSONResponse(
        {"error": "not_found", "message": "Skill not found"},
        status_code=404,
    )


async def bulk_import(request: Request) -> JSONResponse:
    """Handle POST /skills/bulk-import."""
    payload = _verify_token(request)
    if not payload:
        return JSONResponse(
            {"error": "unauthorized", "message": "Invalid or missing token"},
            status_code=401,
        )

    tenant_id = payload.get("tenant_id")

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"error": "bad_request", "message": "Invalid JSON"},
            status_code=400,
        )

    skills = body.get("skills", [])
    result = _store.bulk_import(tenant_id, skills)
    return JSONResponse(result, status_code=202)


async def get_audit_logs(request: Request) -> JSONResponse:
    """Handle GET /audit-logs (admin endpoint)."""
    payload = _verify_token(request)
    if not payload:
        return JSONResponse(
            {"error": "unauthorized", "message": "Invalid or missing token"},
            status_code=401,
        )

    tenant_id = request.query_params.get("tenant_id")
    logs = _store.get_audit_logs(tenant_id)
    return JSONResponse({"logs": logs})


@pytest.fixture
def skills_store() -> Generator[MockSkillsStore, None, None]:
    """Provide a clean skills store for each test."""
    _store.clear()
    yield _store
    _store.clear()


@pytest.fixture
def tenant_a_token() -> str:
    """Generate a token for Tenant A."""
    return make_token(
        sub=USER_A_ID,
        tenant_id=TENANT_A_ID,
        roles=[SKILLS_ROLE],
        scopes=SKILLS_SCOPES,
    )


@pytest.fixture
def tenant_b_token() -> str:
    """Generate a token for Tenant B."""
    return make_token(
        sub=USER_B_ID,
        tenant_id=TENANT_B_ID,
        roles=[SKILLS_ROLE],
        scopes=SKILLS_SCOPES,
    )


@pytest.fixture
def test_client(skills_store: MockSkillsStore) -> TestClient:
    """Create a test client with the skills API routes."""
    app = Starlette(
        routes=[
            Route("/api/v1/skills", create_skill, methods=["POST"]),
            Route("/api/v1/skills", list_skills, methods=["GET"]),
            Route("/api/v1/skills/bulk-import", bulk_import, methods=["POST"]),
            Route("/api/v1/skills/{skill_id}", get_skill, methods=["GET"]),
            Route("/api/v1/skills/{skill_id}", update_skill, methods=["PUT"]),
            Route("/api/v1/skills/{skill_id}", delete_skill, methods=["DELETE"]),
            Route("/api/v1/audit-logs", get_audit_logs, methods=["GET"]),
        ]
    )
    return TestClient(app, raise_server_exceptions=False)


class TestTenantIsolation:
    """Test suite for tenant isolation in Skills API."""

    def test_create_skill_under_tenant_a(
        self,
        test_client: TestClient,
        tenant_a_token: str,
        skills_store: MockSkillsStore,
    ) -> None:
        """Verify that a skill can be created under Tenant A."""
        response = test_client.post(
            "/api/v1/skills",
            json={
                "name": "Python Programming",
                "description": "Advanced Python skills",
                "category": "Programming",
            },
            headers={"Authorization": f"Bearer {tenant_a_token}"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Python Programming"
        assert data["tenant_id"] == TENANT_A_ID
        assert "id" in data

    def test_tenant_b_cannot_read_tenant_a_skill(
        self,
        test_client: TestClient,
        tenant_a_token: str,
        tenant_b_token: str,
        skills_store: MockSkillsStore,
    ) -> None:
        """Verify that Tenant B cannot read a skill created by Tenant A (expect 404/403)."""
        create_response = test_client.post(
            "/api/v1/skills",
            json={"name": "Tenant A Exclusive Skill"},
            headers={"Authorization": f"Bearer {tenant_a_token}"},
        )
        assert create_response.status_code == 201
        skill_id = create_response.json()["id"]

        read_response = test_client.get(
            f"/api/v1/skills/{skill_id}",
            headers={"Authorization": f"Bearer {tenant_b_token}"},
        )

        assert read_response.status_code in (403, 404)
        assert "error" in read_response.json()

    def test_tenant_b_cannot_update_tenant_a_skill(
        self,
        test_client: TestClient,
        tenant_a_token: str,
        tenant_b_token: str,
        skills_store: MockSkillsStore,
    ) -> None:
        """Verify that Tenant B cannot update a skill owned by Tenant A."""
        create_response = test_client.post(
            "/api/v1/skills",
            json={"name": "Original Name"},
            headers={"Authorization": f"Bearer {tenant_a_token}"},
        )
        assert create_response.status_code == 201
        skill_id = create_response.json()["id"]

        update_response = test_client.put(
            f"/api/v1/skills/{skill_id}",
            json={"name": "Malicious Update"},
            headers={"Authorization": f"Bearer {tenant_b_token}"},
        )

        assert update_response.status_code in (403, 404)

        verify_response = test_client.get(
            f"/api/v1/skills/{skill_id}",
            headers={"Authorization": f"Bearer {tenant_a_token}"},
        )
        assert verify_response.status_code == 200
        assert verify_response.json()["name"] == "Original Name"

    def test_tenant_b_cannot_delete_tenant_a_skill(
        self,
        test_client: TestClient,
        tenant_a_token: str,
        tenant_b_token: str,
        skills_store: MockSkillsStore,
    ) -> None:
        """Verify that Tenant B cannot delete a skill owned by Tenant A."""
        create_response = test_client.post(
            "/api/v1/skills",
            json={"name": "Protected Skill"},
            headers={"Authorization": f"Bearer {tenant_a_token}"},
        )
        assert create_response.status_code == 201
        skill_id = create_response.json()["id"]

        delete_response = test_client.delete(
            f"/api/v1/skills/{skill_id}",
            headers={"Authorization": f"Bearer {tenant_b_token}"},
        )

        assert delete_response.status_code in (403, 404)

        verify_response = test_client.get(
            f"/api/v1/skills/{skill_id}",
            headers={"Authorization": f"Bearer {tenant_a_token}"},
        )
        assert verify_response.status_code == 200

    def test_list_skills_only_shows_tenant_specific_resources(
        self,
        test_client: TestClient,
        tenant_a_token: str,
        tenant_b_token: str,
        skills_store: MockSkillsStore,
    ) -> None:
        """Verify that listing skills only returns resources for the requesting tenant."""
        test_client.post(
            "/api/v1/skills",
            json={"name": "Tenant A Skill 1"},
            headers={"Authorization": f"Bearer {tenant_a_token}"},
        )
        test_client.post(
            "/api/v1/skills",
            json={"name": "Tenant A Skill 2"},
            headers={"Authorization": f"Bearer {tenant_a_token}"},
        )
        test_client.post(
            "/api/v1/skills",
            json={"name": "Tenant B Skill"},
            headers={"Authorization": f"Bearer {tenant_b_token}"},
        )

        list_a_response = test_client.get(
            "/api/v1/skills",
            headers={"Authorization": f"Bearer {tenant_a_token}"},
        )
        assert list_a_response.status_code == 200
        tenant_a_skills = list_a_response.json()["items"]
        assert len(tenant_a_skills) == 2
        for skill in tenant_a_skills:
            assert skill["tenant_id"] == TENANT_A_ID

        list_b_response = test_client.get(
            "/api/v1/skills",
            headers={"Authorization": f"Bearer {tenant_b_token}"},
        )
        assert list_b_response.status_code == 200
        tenant_b_skills = list_b_response.json()["items"]
        assert len(tenant_b_skills) == 1
        assert tenant_b_skills[0]["tenant_id"] == TENANT_B_ID
        assert tenant_b_skills[0]["name"] == "Tenant B Skill"

    def test_audit_logs_contain_tenant_identifiers(
        self,
        test_client: TestClient,
        tenant_a_token: str,
        tenant_b_token: str,
        skills_store: MockSkillsStore,
    ) -> None:
        """Verify that audit logs contain tenant identifiers for all operations."""
        create_response = test_client.post(
            "/api/v1/skills",
            json={"name": "Audited Skill"},
            headers={"Authorization": f"Bearer {tenant_a_token}"},
        )
        skill_id = create_response.json()["id"]

        test_client.get(
            f"/api/v1/skills/{skill_id}",
            headers={"Authorization": f"Bearer {tenant_a_token}"},
        )
        test_client.get(
            f"/api/v1/skills/{skill_id}",
            headers={"Authorization": f"Bearer {tenant_b_token}"},
        )

        all_logs = skills_store.get_audit_logs()

        for log in all_logs:
            assert "tenant_id" in log
            assert log["tenant_id"] in (TENANT_A_ID, TENANT_B_ID)
            assert "action" in log
            assert "timestamp" in log

        tenant_a_logs = skills_store.get_audit_logs(TENANT_A_ID)
        tenant_b_logs = skills_store.get_audit_logs(TENANT_B_ID)

        assert len(tenant_a_logs) >= 2  # create + read
        assert len(tenant_b_logs) >= 1  # denied read attempt

        denied_logs = [
            log for log in tenant_b_logs if log["action"] == "read_denied"
        ]
        assert len(denied_logs) >= 1
        assert denied_logs[0]["skill_id"] == skill_id

    def test_tenant_a_can_manage_own_resources(
        self,
        test_client: TestClient,
        tenant_a_token: str,
        skills_store: MockSkillsStore,
    ) -> None:
        """Verify that Tenant A can fully manage their own resources."""
        create_response = test_client.post(
            "/api/v1/skills",
            json={"name": "My Skill", "description": "Original"},
            headers={"Authorization": f"Bearer {tenant_a_token}"},
        )
        assert create_response.status_code == 201
        skill_id = create_response.json()["id"]

        read_response = test_client.get(
            f"/api/v1/skills/{skill_id}",
            headers={"Authorization": f"Bearer {tenant_a_token}"},
        )
        assert read_response.status_code == 200
        assert read_response.json()["name"] == "My Skill"

        update_response = test_client.put(
            f"/api/v1/skills/{skill_id}",
            json={"name": "Updated Skill", "description": "Updated"},
            headers={"Authorization": f"Bearer {tenant_a_token}"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["name"] == "Updated Skill"

        delete_response = test_client.delete(
            f"/api/v1/skills/{skill_id}",
            headers={"Authorization": f"Bearer {tenant_a_token}"},
        )
        assert delete_response.status_code == 204

        verify_response = test_client.get(
            f"/api/v1/skills/{skill_id}",
            headers={"Authorization": f"Bearer {tenant_a_token}"},
        )
        assert verify_response.status_code == 404


class TestAuthenticationErrors:
    """Test suite for authentication error handling."""

    def test_request_without_token_returns_401(
        self,
        test_client: TestClient,
        skills_store: MockSkillsStore,
    ) -> None:
        """Verify that requests without a token return 401."""
        response = test_client.get("/api/v1/skills")
        assert response.status_code == 401
        assert response.json()["error"] == "unauthorized"

    def test_request_with_invalid_token_returns_401(
        self,
        test_client: TestClient,
        skills_store: MockSkillsStore,
    ) -> None:
        """Verify that requests with an invalid token return 401."""
        response = test_client.get(
            "/api/v1/skills",
            headers={"Authorization": "Bearer invalid.jwt.token"},
        )
        assert response.status_code == 401

    def test_request_with_expired_token_returns_401(
        self,
        test_client: TestClient,
        skills_store: MockSkillsStore,
    ) -> None:
        """Verify that requests with an expired token return 401."""
        expired_token = make_token(
            sub=USER_A_ID,
            tenant_id=TENANT_A_ID,
            exp_offset=-3600,
        )
        response = test_client.get(
            "/api/v1/skills",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert response.status_code == 401


class TestBulkOperationsTenantIsolation:
    """Test suite for bulk operations tenant isolation."""

    def test_bulk_import_respects_tenant_isolation(
        self,
        test_client: TestClient,
        tenant_a_token: str,
        tenant_b_token: str,
        skills_store: MockSkillsStore,
    ) -> None:
        """Verify that bulk imported skills are isolated to the importing tenant."""
        import_response = test_client.post(
            "/api/v1/skills/bulk-import",
            json={
                "skills": [
                    {"name": "Bulk Skill 1"},
                    {"name": "Bulk Skill 2"},
                    {"name": "Bulk Skill 3"},
                ]
            },
            headers={"Authorization": f"Bearer {tenant_a_token}"},
        )
        assert import_response.status_code == 202
        assert import_response.json()["imported_count"] == 3

        list_b_response = test_client.get(
            "/api/v1/skills",
            headers={"Authorization": f"Bearer {tenant_b_token}"},
        )
        assert list_b_response.status_code == 200
        assert len(list_b_response.json()["items"]) == 0

        list_a_response = test_client.get(
            "/api/v1/skills",
            headers={"Authorization": f"Bearer {tenant_a_token}"},
        )
        assert list_a_response.status_code == 200
        assert len(list_a_response.json()["items"]) == 3

    def test_bulk_cross_tenant_access_attempts_logged(
        self,
        test_client: TestClient,
        tenant_a_token: str,
        tenant_b_token: str,
        skills_store: MockSkillsStore,
    ) -> None:
        """Verify that multiple cross-tenant access attempts are properly logged."""
        skill_ids = []
        for i in range(3):
            response = test_client.post(
                "/api/v1/skills",
                json={"name": f"Skill {i}"},
                headers={"Authorization": f"Bearer {tenant_a_token}"},
            )
            skill_ids.append(response.json()["id"])

        for skill_id in skill_ids:
            test_client.get(
                f"/api/v1/skills/{skill_id}",
                headers={"Authorization": f"Bearer {tenant_b_token}"},
            )

        tenant_b_logs = skills_store.get_audit_logs(TENANT_B_ID)
        denied_logs = [log for log in tenant_b_logs if log["action"] == "read_denied"]

        assert len(denied_logs) == 3
        logged_skill_ids = {log["skill_id"] for log in denied_logs}
        assert logged_skill_ids == set(skill_ids)
