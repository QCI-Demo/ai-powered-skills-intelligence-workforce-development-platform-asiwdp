"""Unit tests for JWT authentication middleware HTTP outcomes."""

from __future__ import annotations

import jwt
from starlette.testclient import TestClient

from tests.conftest import TEST_SECRET, make_token


class TestValidToken:
    def test_valid_token_returns_200(self, app_client: TestClient) -> None:
        token = make_token(roles=["learner"], scopes=["skills:read"])
        response = app_client.get(
            "/api/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["tenant_id"] == "22222222-2222-2222-2222-222222222222"
        assert "learner" in body["roles"]
        # learner role expands to progress:write etc.
        assert "progress:write" in body["permissions"]
        assert "skills:read" in body["permissions"]

    def test_public_health_skips_auth(self, app_client: TestClient) -> None:
        response = app_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "up"

    def test_camel_case_tenant_claim_accepted(self, app_client: TestClient) -> None:
        token = make_token(
            roles=["learner"],
            extra={"tenantId": "22222222-2222-2222-2222-222222222222"},
        )
        # Remove snake_case so only camelCase remains — rebuild payload
        import time

        now = int(time.time())
        payload = {
            "sub": "11111111-1111-1111-1111-111111111111",
            "tenantId": "22222222-2222-2222-2222-222222222222",
            "iat": now,
            "exp": now + 3600,
            "iss": "https://auth.asiwdp.test/",
            "aud": "asiwdp-api",
            "roles": ["learner"],
            "scopes": [],
        }
        token = jwt.encode(payload, TEST_SECRET, algorithm="HS256")
        response = app_client.get(
            "/api/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["tenant_id"] == "22222222-2222-2222-2222-222222222222"


class TestMissingToken:
    def test_missing_authorization_returns_401(self, app_client: TestClient) -> None:
        response = app_client.get("/api/me")
        assert response.status_code == 401
        assert response.json()["error"] == "token_missing"
        assert "WWW-Authenticate" in response.headers

    def test_non_bearer_scheme_returns_401(self, app_client: TestClient) -> None:
        response = app_client.get(
            "/api/me", headers={"Authorization": "Basic abc"}
        )
        assert response.status_code == 401
        assert response.json()["error"] == "token_missing"


class TestExpiredToken:
    def test_expired_token_returns_401(self, app_client: TestClient) -> None:
        token = make_token(exp_offset=-120, iat_offset=-600)
        response = app_client.get(
            "/api/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401
        assert response.json()["error"] == "token_expired"


class TestTamperedToken:
    def test_tampered_signature_returns_401(self, app_client: TestClient) -> None:
        token = make_token(roles=["tenant_admin"])
        # Flip a character in the signature segment
        header, payload, signature = token.split(".")
        tampered = f"{header}.{payload}.{signature[:-2]}ab"
        response = app_client.get(
            "/api/me", headers={"Authorization": f"Bearer {tampered}"}
        )
        assert response.status_code == 401
        assert response.json()["error"] == "token_invalid"

    def test_wrong_secret_returns_401(self, app_client: TestClient) -> None:
        token = make_token(secret="wrong-secret-value-for-tamper-test")
        response = app_client.get(
            "/api/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401
        assert response.json()["error"] == "token_invalid"

    def test_wrong_issuer_returns_401(self, app_client: TestClient) -> None:
        token = make_token(issuer="https://evil.example/")
        response = app_client.get(
            "/api/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401
        assert response.json()["error"] == "token_invalid"

    def test_wrong_audience_returns_401(self, app_client: TestClient) -> None:
        token = make_token(audience="other-api")
        response = app_client.get(
            "/api/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401
        assert response.json()["error"] == "token_invalid"


class TestRbacDenial:
    def test_learner_denied_skills_write_returns_403(
        self, app_client: TestClient
    ) -> None:
        token = make_token(roles=["learner"])
        response = app_client.post(
            "/api/skills", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403
        assert response.json()["error"] == "forbidden"

    def test_skills_manager_allowed_skills_write(
        self, app_client: TestClient
    ) -> None:
        token = make_token(roles=["skills_manager"])
        response = app_client.post(
            "/api/skills", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["action"] == "skills:write"

    def test_middleware_required_permission_denies_learner(
        self, rbac_app_client: TestClient
    ) -> None:
        token = make_token(roles=["learner"])
        response = rbac_app_client.get(
            "/api/admin", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403
        assert response.json()["error"] == "forbidden"

    def test_middleware_required_permission_allows_tenant_admin(
        self, rbac_app_client: TestClient
    ) -> None:
        token = make_token(roles=["tenant_admin"])
        response = rbac_app_client.get(
            "/api/admin", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["ok"] is True
