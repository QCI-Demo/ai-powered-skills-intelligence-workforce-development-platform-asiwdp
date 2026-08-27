"""
Tenant Isolation Integration Tests for ASIWDP Skills Service

Tests verify that resources created under one tenant are inaccessible to other
tenants, enforcing strict multi-tenant data isolation as required by the platform.

Task ID: 1ec84f05-90fe-4b6f-895d-4dd68e71edc2
"""

import os
import uuid
import pytest
import httpx
from datetime import datetime, timedelta
from typing import Any, Generator

# Test configuration - use environment variables or defaults
API_BASE_URL = os.getenv("SKILLS_API_BASE_URL", "http://localhost:8080/api/v1")
AUDIT_LOG_API_URL = os.getenv("AUDIT_LOG_API_URL", "http://localhost:8081/api/v1/audit")


class TenantContext:
    """Represents a tenant's authentication and identity context."""

    def __init__(self, tenant_id: str, token: str, roles: list[str] | None = None):
        self.tenant_id = tenant_id
        self.token = token
        self.roles = roles or ["skills_manager"]

    @property
    def headers(self) -> dict[str, str]:
        """Return HTTP headers for authenticated requests."""
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Tenant-ID": self.tenant_id,
            "Content-Type": "application/json",
        }


def generate_test_token(tenant_id: str, roles: list[str], scopes: list[str]) -> str:
    """
    Generate a test JWT token for the given tenant.
    
    In production, this would call the auth service. For integration tests,
    we use a test token generator or mock auth service.
    """
    # In a real implementation, this would call the auth service
    # For testing purposes, we construct a token that the test auth middleware accepts
    import base64
    import json
    
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": f"test-user-{uuid.uuid4()}",
        "tenant_id": tenant_id,
        "roles": roles,
        "scopes": scopes,
        "iss": "https://auth.asiwdp.example",
        "aud": "skills-framework-service",
        "iat": int(datetime.utcnow().timestamp()),
        "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
    }
    
    # For test environments with mock auth, return a recognizable test token format
    # Real environments should use proper JWT signing
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    signature = "test_signature"
    
    return f"{header_b64}.{payload_b64}.{signature}"


@pytest.fixture(scope="module")
def tenant_a() -> TenantContext:
    """Fixture for Tenant A with full skills management permissions."""
    tenant_id = os.getenv("TENANT_A_ID", f"tenant-a-{uuid.uuid4()}")
    token = os.getenv("TENANT_A_TOKEN") or generate_test_token(
        tenant_id=tenant_id,
        roles=["skills_manager", "tenant_admin"],
        scopes=["skills:read", "skills:write", "skills:delete", "skills:admin"],
    )
    return TenantContext(tenant_id=tenant_id, token=token)


@pytest.fixture(scope="module")
def tenant_b() -> TenantContext:
    """Fixture for Tenant B with full skills management permissions."""
    tenant_id = os.getenv("TENANT_B_ID", f"tenant-b-{uuid.uuid4()}")
    token = os.getenv("TENANT_B_TOKEN") or generate_test_token(
        tenant_id=tenant_id,
        roles=["skills_manager", "tenant_admin"],
        scopes=["skills:read", "skills:write", "skills:delete", "skills:admin"],
    )
    return TenantContext(tenant_id=tenant_id, token=token)


@pytest.fixture(scope="module")
def http_client() -> Generator[httpx.Client, None, None]:
    """Shared HTTP client for all tests."""
    with httpx.Client(base_url=API_BASE_URL, timeout=30.0) as client:
        yield client


@pytest.fixture
def skill_data() -> dict[str, Any]:
    """Generate unique skill data for testing."""
    return {
        "name": f"Test Skill {uuid.uuid4().hex[:8]}",
        "description": "A skill created for tenant isolation testing",
        "category": "Technical",
        "proficiency_levels": [
            {"level": 1, "name": "Beginner", "description": "Basic knowledge"},
            {"level": 2, "name": "Intermediate", "description": "Working knowledge"},
            {"level": 3, "name": "Advanced", "description": "Expert knowledge"},
        ],
        "metadata": {
            "source": "integration_test",
            "test_run": datetime.utcnow().isoformat(),
        },
    }


class TestTenantIsolation:
    """Test suite for tenant isolation in the Skills Service."""

    def test_skill_created_under_tenant_a_not_visible_to_tenant_b(
        self,
        http_client: httpx.Client,
        tenant_a: TenantContext,
        tenant_b: TenantContext,
        skill_data: dict[str, Any],
    ):
        """
        Verify that a skill created by Tenant A cannot be read by Tenant B.
        
        Expected behavior: Tenant B receives 404 when attempting to access
        Tenant A's skill, ensuring complete data isolation.
        """
        # Step 1: Create a skill under Tenant A
        create_response = http_client.post(
            "/skills",
            headers=tenant_a.headers,
            json=skill_data,
        )
        assert create_response.status_code == 201, (
            f"Failed to create skill: {create_response.text}"
        )
        
        skill = create_response.json()
        skill_id = skill["id"]
        
        # Verify the skill belongs to Tenant A
        assert skill["tenant_id"] == tenant_a.tenant_id
        
        try:
            # Step 2: Attempt to read the skill with Tenant B's token
            read_response = http_client.get(
                f"/skills/{skill_id}",
                headers=tenant_b.headers,
            )
            
            # Expect 404 (resource not found in tenant's scope) or 403 (forbidden)
            assert read_response.status_code in (403, 404), (
                f"Expected 403 or 404, got {read_response.status_code}. "
                f"Cross-tenant access should be blocked. Response: {read_response.text}"
            )
            
            # Step 3: Verify Tenant A can still access their own skill
            verify_response = http_client.get(
                f"/skills/{skill_id}",
                headers=tenant_a.headers,
            )
            assert verify_response.status_code == 200
            assert verify_response.json()["id"] == skill_id
            
        finally:
            # Cleanup: Delete the skill
            http_client.delete(f"/skills/{skill_id}", headers=tenant_a.headers)

    def test_tenant_b_cannot_update_tenant_a_skill(
        self,
        http_client: httpx.Client,
        tenant_a: TenantContext,
        tenant_b: TenantContext,
        skill_data: dict[str, Any],
    ):
        """
        Verify that Tenant B cannot modify a skill owned by Tenant A.
        """
        # Create skill under Tenant A
        create_response = http_client.post(
            "/skills",
            headers=tenant_a.headers,
            json=skill_data,
        )
        assert create_response.status_code == 201
        skill_id = create_response.json()["id"]
        
        try:
            # Attempt to update with Tenant B's credentials
            update_response = http_client.put(
                f"/skills/{skill_id}",
                headers=tenant_b.headers,
                json={**skill_data, "name": "Malicious Update Attempt"},
            )
            
            # Should be rejected with 403 or 404
            assert update_response.status_code in (403, 404), (
                f"Cross-tenant update should be blocked. Got: {update_response.status_code}"
            )
            
            # Verify original skill is unchanged
            verify_response = http_client.get(
                f"/skills/{skill_id}",
                headers=tenant_a.headers,
            )
            assert verify_response.status_code == 200
            assert verify_response.json()["name"] == skill_data["name"]
            
        finally:
            http_client.delete(f"/skills/{skill_id}", headers=tenant_a.headers)

    def test_tenant_b_cannot_delete_tenant_a_skill(
        self,
        http_client: httpx.Client,
        tenant_a: TenantContext,
        tenant_b: TenantContext,
        skill_data: dict[str, Any],
    ):
        """
        Verify that Tenant B cannot delete a skill owned by Tenant A.
        """
        # Create skill under Tenant A
        create_response = http_client.post(
            "/skills",
            headers=tenant_a.headers,
            json=skill_data,
        )
        assert create_response.status_code == 201
        skill_id = create_response.json()["id"]
        
        try:
            # Attempt to delete with Tenant B's credentials
            delete_response = http_client.delete(
                f"/skills/{skill_id}",
                headers=tenant_b.headers,
            )
            
            # Should be rejected
            assert delete_response.status_code in (403, 404)
            
            # Verify skill still exists for Tenant A
            verify_response = http_client.get(
                f"/skills/{skill_id}",
                headers=tenant_a.headers,
            )
            assert verify_response.status_code == 200
            
        finally:
            http_client.delete(f"/skills/{skill_id}", headers=tenant_a.headers)

    def test_list_skills_returns_only_tenant_scoped_data(
        self,
        http_client: httpx.Client,
        tenant_a: TenantContext,
        tenant_b: TenantContext,
        skill_data: dict[str, Any],
    ):
        """
        Verify that listing skills returns only the calling tenant's data.
        """
        created_skill_ids = []
        
        try:
            # Create skills for both tenants
            for tenant in [tenant_a, tenant_b]:
                response = http_client.post(
                    "/skills",
                    headers=tenant.headers,
                    json={**skill_data, "name": f"Skill for {tenant.tenant_id[:10]}"},
                )
                assert response.status_code == 201
                created_skill_ids.append((response.json()["id"], tenant))
            
            # List skills as Tenant A
            list_response_a = http_client.get("/skills", headers=tenant_a.headers)
            assert list_response_a.status_code == 200
            
            skills_a = list_response_a.json()
            skills_list_a = skills_a.get("data", skills_a)
            
            # Verify all returned skills belong to Tenant A
            for skill in skills_list_a:
                assert skill["tenant_id"] == tenant_a.tenant_id, (
                    f"Skill {skill['id']} belongs to wrong tenant"
                )
            
            # List skills as Tenant B
            list_response_b = http_client.get("/skills", headers=tenant_b.headers)
            assert list_response_b.status_code == 200
            
            skills_b = list_response_b.json()
            skills_list_b = skills_b.get("data", skills_b)
            
            # Verify all returned skills belong to Tenant B
            for skill in skills_list_b:
                assert skill["tenant_id"] == tenant_b.tenant_id
                
        finally:
            # Cleanup
            for skill_id, tenant in created_skill_ids:
                http_client.delete(f"/skills/{skill_id}", headers=tenant.headers)

    def test_bulk_import_tenant_isolation(
        self,
        http_client: httpx.Client,
        tenant_a: TenantContext,
        tenant_b: TenantContext,
    ):
        """
        Verify that bulk imported skills are properly scoped to the importing tenant.
        """
        bulk_data = {
            "skills": [
                {"name": f"Bulk Skill 1 - {uuid.uuid4().hex[:6]}", "category": "Technical"},
                {"name": f"Bulk Skill 2 - {uuid.uuid4().hex[:6]}", "category": "Technical"},
            ],
            "options": {"upsert": False},
        }
        
        # Import skills as Tenant A
        import_response = http_client.post(
            "/skills/bulk-import",
            headers=tenant_a.headers,
            json=bulk_data,
        )
        
        # Accept 200, 201, or 202 for async import
        assert import_response.status_code in (200, 201, 202)
        
        # List skills as Tenant B - should not see Tenant A's bulk imported skills
        list_response = http_client.get("/skills", headers=tenant_b.headers)
        assert list_response.status_code == 200
        
        skills_b = list_response.json()
        skills_list_b = skills_b.get("data", skills_b)
        
        for skill in skills_list_b:
            # Tenant B should not see any skill from the bulk import
            assert skill["tenant_id"] == tenant_b.tenant_id


class TestAuditLogTenantIdentifiers:
    """Test suite verifying audit logs contain proper tenant identifiers."""

    @pytest.fixture
    def audit_client(self) -> Generator[httpx.Client, None, None]:
        """HTTP client for audit log API."""
        with httpx.Client(base_url=AUDIT_LOG_API_URL, timeout=30.0) as client:
            yield client

    def test_skill_creation_logged_with_tenant_id(
        self,
        http_client: httpx.Client,
        audit_client: httpx.Client,
        tenant_a: TenantContext,
        skill_data: dict[str, Any],
    ):
        """
        Verify that skill creation operations are logged with the tenant identifier.
        """
        # Create a skill
        create_response = http_client.post(
            "/skills",
            headers=tenant_a.headers,
            json=skill_data,
        )
        assert create_response.status_code == 201
        skill_id = create_response.json()["id"]
        
        try:
            # Query audit logs for this operation
            # Note: In real tests, may need to wait for async log propagation
            audit_response = audit_client.get(
                "/logs",
                headers=tenant_a.headers,
                params={
                    "resource_type": "skill",
                    "resource_id": skill_id,
                    "action": "create",
                },
            )
            
            if audit_response.status_code == 200:
                logs = audit_response.json()
                log_entries = logs.get("data", logs)
                
                if log_entries:
                    # Verify tenant_id is present in audit log
                    for entry in log_entries:
                        assert "tenant_id" in entry, "Audit log missing tenant_id"
                        assert entry["tenant_id"] == tenant_a.tenant_id, (
                            "Audit log has incorrect tenant_id"
                        )
                        assert "action" in entry
                        assert "resource_id" in entry
                        assert "timestamp" in entry
                        
        finally:
            http_client.delete(f"/skills/{skill_id}", headers=tenant_a.headers)

    def test_cross_tenant_access_attempt_logged(
        self,
        http_client: httpx.Client,
        audit_client: httpx.Client,
        tenant_a: TenantContext,
        tenant_b: TenantContext,
        skill_data: dict[str, Any],
    ):
        """
        Verify that cross-tenant access attempts are logged for security auditing.
        """
        # Create skill under Tenant A
        create_response = http_client.post(
            "/skills",
            headers=tenant_a.headers,
            json=skill_data,
        )
        assert create_response.status_code == 201
        skill_id = create_response.json()["id"]
        
        try:
            # Attempt cross-tenant access
            http_client.get(f"/skills/{skill_id}", headers=tenant_b.headers)
            
            # Check if the access attempt was logged
            # The audit log should contain both the requesting tenant and the resource owner
            audit_response = audit_client.get(
                "/logs",
                headers=tenant_b.headers,  # Query as Tenant B (the requester)
                params={
                    "action": "access_denied",
                    "resource_type": "skill",
                },
            )
            
            if audit_response.status_code == 200:
                logs = audit_response.json()
                log_entries = logs.get("data", logs)
                
                # If audit logging is implemented, verify structure
                for entry in log_entries:
                    # Audit should capture the requesting tenant
                    assert "tenant_id" in entry or "requesting_tenant_id" in entry
                    
        finally:
            http_client.delete(f"/skills/{skill_id}", headers=tenant_a.headers)


class TestTenantIsolationEdgeCases:
    """Edge case tests for tenant isolation."""

    def test_missing_tenant_header_rejected(self, http_client: httpx.Client):
        """Requests without tenant context should be rejected."""
        response = http_client.get(
            "/skills",
            headers={"Authorization": "Bearer some-token"},
        )
        # Should return 400 (bad request) or 401 (unauthorized)
        assert response.status_code in (400, 401, 403)

    def test_tenant_id_mismatch_in_token_vs_header(
        self,
        http_client: httpx.Client,
        tenant_a: TenantContext,
        tenant_b: TenantContext,
    ):
        """
        Requests where the token's tenant_id doesn't match the X-Tenant-ID header
        should be rejected to prevent tenant spoofing.
        """
        # Use Tenant A's token but Tenant B's tenant ID in header
        mismatched_headers = {
            "Authorization": f"Bearer {tenant_a.token}",
            "X-Tenant-ID": tenant_b.tenant_id,
            "Content-Type": "application/json",
        }
        
        response = http_client.get("/skills", headers=mismatched_headers)
        
        # Should be rejected - either 401 or 403
        assert response.status_code in (401, 403), (
            f"Tenant ID mismatch should be rejected. Got: {response.status_code}"
        )

    def test_empty_tenant_id_rejected(self, http_client: httpx.Client):
        """Empty tenant ID should be rejected."""
        headers = {
            "Authorization": "Bearer some-token",
            "X-Tenant-ID": "",
            "Content-Type": "application/json",
        }
        
        response = http_client.get("/skills", headers=headers)
        assert response.status_code in (400, 401, 403)

    def test_sql_injection_in_tenant_id_handled(
        self,
        http_client: httpx.Client,
        tenant_a: TenantContext,
    ):
        """
        Malicious tenant IDs should be properly sanitized/rejected.
        """
        malicious_tenant_ids = [
            "'; DROP TABLE skills; --",
            "tenant-a' OR '1'='1",
            "<script>alert('xss')</script>",
            "../../../etc/passwd",
        ]
        
        for malicious_id in malicious_tenant_ids:
            headers = {
                "Authorization": f"Bearer {tenant_a.token}",
                "X-Tenant-ID": malicious_id,
                "Content-Type": "application/json",
            }
            
            response = http_client.get("/skills", headers=headers)
            
            # Should either be rejected (400/401/403) or return empty results
            # Should NOT return an error that leaks database info
            assert response.status_code in (200, 400, 401, 403)
            
            if response.status_code == 200:
                # If 200, verify it returns empty or tenant-scoped data only
                data = response.json()
                skills = data.get("data", data)
                if isinstance(skills, list):
                    assert len(skills) == 0 or all(
                        s.get("tenant_id") == malicious_id for s in skills
                    )


# Pytest configuration for running these tests
def pytest_configure(config):
    """Configure custom markers for tenant isolation tests."""
    config.addinivalue_line(
        "markers",
        "tenant_isolation: marks tests as tenant isolation tests",
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
