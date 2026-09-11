"""Integration API service tests: JWT, tenant context, scopes, X-API-Version."""

from __future__ import annotations

import time
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient

from asiwdp_auth import API_VERSION_HEADER, AuthConfig
from asiwdp_integration_api.app import create_app

REPO_ROOT = Path(__file__).resolve().parents[3]
RBAC_MATRIX = REPO_ROOT / "config" / "rbac" / "role-permission-matrix.yaml"

TEST_SECRET = "test-only-hs256-secret-not-for-production"
TEST_ISSUER = "https://auth.asiwdp.test/"
TEST_AUDIENCE = "asiwdp-api"
TENANT = "22222222-2222-2222-2222-222222222222"


def make_token(
    *,
    roles: list[str] | None = None,
    scopes: list[str] | None = None,
    tenant_id: str = TENANT,
) -> str:
    now = int(time.time())
    payload = {
        "sub": "11111111-1111-1111-1111-111111111111",
        "tenant_id": tenant_id,
        "iat": now,
        "exp": now + 3600,
        "iss": TEST_ISSUER,
        "aud": TEST_AUDIENCE,
        "roles": roles or ["service_account"],
        "scopes": scopes or [],
    }
    return jwt.encode(payload, TEST_SECRET, algorithm="HS256")


def envelope(**overrides):
    base = {
        "tenantId": TENANT,
        "sourceSystem": "workday",
        "sourceRecordId": "E-100",
        "idempotencyKey": "idem-1",
        "capturedAt": "2026-09-11T12:00:00Z",
    }
    base.update(overrides)
    return base


@pytest.fixture
def client() -> TestClient:
    config = AuthConfig(
        issuer=TEST_ISSUER,
        audience=TEST_AUDIENCE,
        verification_key=TEST_SECRET,
        algorithm="HS256",
        leeway_seconds=0,
        require_tenant=True,
    )
    app = create_app(auth_config=config, rbac_matrix_path=RBAC_MATRIX)
    return TestClient(app)


class TestHealthAndVersionHeader:
    def test_root_health_returns_version_header(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.headers.get(API_VERSION_HEADER) == "v1"

    def test_v2_health_returns_v2_header(self, client: TestClient) -> None:
        response = client.get("/api/v2/health")
        assert response.status_code == 200
        assert response.headers.get(API_VERSION_HEADER) == "v2"
        assert response.json()["apiVersion"] == "v2"


class TestJwtAndScopes:
    def test_missing_token_401_with_version_header(self, client: TestClient) -> None:
        response = client.post("/api/v1/hris/employees", json={})
        assert response.status_code == 401
        assert response.headers.get(API_VERSION_HEADER) == "v1"

    def test_v1_employee_ingest_with_hris_write(self, client: TestClient) -> None:
        token = make_token(scopes=["hris:write"])
        body = {
            **envelope(),
            "employeeNumber": "E100",
            "displayName": "Alex Example",
        }
        response = client.post(
            "/api/v1/hris/employees",
            headers={"Authorization": f"Bearer {token}"},
            json=body,
        )
        assert response.status_code == 202
        assert response.headers.get(API_VERSION_HEADER) == "v1"
        assert response.json()["tenantId"] == TENANT
        assert response.json()["apiVersion"] == "v1"

    def test_scope_denied_without_hris_write(self, client: TestClient) -> None:
        token = make_token(roles=["learner"], scopes=["skills:read"])
        body = {
            **envelope(),
            "employeeNumber": "E100",
            "displayName": "Alex Example",
        }
        response = client.post(
            "/api/v1/hris/employees",
            headers={"Authorization": f"Bearer {token}"},
            json=body,
        )
        assert response.status_code == 403
        assert response.json()["error"] == "scope_denied"

    def test_tenant_mismatch_forbidden(self, client: TestClient) -> None:
        token = make_token(scopes=["hris:write"])
        body = {
            **envelope(tenantId="99999999-9999-9999-9999-999999999999"),
            "employeeNumber": "E100",
            "displayName": "Alex Example",
        }
        response = client.post(
            "/api/v1/hris/employees",
            headers={"Authorization": f"Bearer {token}"},
            json=body,
        )
        assert response.status_code == 403
        assert response.json()["detail"]["error"] == "tenant_mismatch"

    def test_service_account_role_grants_hris_write(self, client: TestClient) -> None:
        # No explicit scopes — role expansion should allow write
        token = make_token(roles=["service_account"], scopes=[])
        body = {
            **envelope(),
            "employeeNumber": "E100",
            "displayName": "Alex Example",
        }
        response = client.post(
            "/api/v1/hris/employees",
            headers={"Authorization": f"Bearer {token}"},
            json=body,
        )
        assert response.status_code == 202


class TestV2Controllers:
    def test_hris_batch_returns_v2_header(self, client: TestClient) -> None:
        token = make_token(scopes=["hris:write"])
        record = {
            **envelope(sourceRecordId="E-200", idempotencyKey="idem-2"),
            "employeeNumber": "E200",
            "displayName": "Blake Example",
        }
        response = client.post(
            "/api/v2/hris/employees/batch",
            headers={"Authorization": f"Bearer {token}"},
            json={"correlationId": "corr-1", "records": [record]},
        )
        assert response.status_code == 202
        assert response.headers.get(API_VERSION_HEADER) == "v2"
        body = response.json()
        assert body["apiVersion"] == "v2"
        assert body["acceptedCount"] == 1
        assert "statusHref" in body

    def test_credential_rotate_requires_scope(self, client: TestClient) -> None:
        token = make_token(scopes=["content:write"])
        response = client.post(
            "/api/v1/integrations/credentials/rotate",
            headers={"Authorization": f"Bearer {token}"},
            json={"provider": "cornerstone", "credentialRef": "sm://integrations/cs/1"},
        )
        assert response.status_code == 403

    def test_credential_rotate_success(self, client: TestClient) -> None:
        token = make_token(
            roles=["tenant_admin"],
            scopes=["integrations:credentials:rotate"],
        )
        response = client.post(
            "/api/v1/integrations/credentials/rotate",
            headers={"Authorization": f"Bearer {token}"},
            json={"provider": "cornerstone", "credentialRef": "sm://integrations/cs/1"},
        )
        assert response.status_code == 202
        payload = response.json()
        assert payload["credentialRef"] == "sm://integrations/cs/1"
        # Opaque refs only — no credential material fields in the response body
        assert "clientSecret" not in payload
        assert "apiKey" not in payload
        assert "password" not in payload
