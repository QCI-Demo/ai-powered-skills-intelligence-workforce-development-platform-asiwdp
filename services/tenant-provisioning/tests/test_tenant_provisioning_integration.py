"""Integration tests for tenant provisioning."""

from __future__ import annotations

import time
from pathlib import Path
from uuid import UUID

import jwt
import pytest
from fastapi.testclient import TestClient

from asiwdp_auth import AuthConfig
from asiwdp_tenant_provisioning.app import create_app
from asiwdp_tenant_provisioning.events import EVENT_CHANNEL, EVENT_TYPE

REPO_ROOT = Path(__file__).resolve().parents[3]
RBAC_MATRIX = REPO_ROOT / "config" / "rbac" / "role-permission-matrix.yaml"

TEST_SECRET = "test-only-hs256-secret-not-for-production"
TEST_ISSUER = "https://auth.asiwdp.test/"
TEST_AUDIENCE = "asiwdp-api"

PLATFORM_TENANT = "22222222-2222-2222-2222-222222222222"
ACTOR_SUB = "11111111-1111-1111-1111-111111111111"


def make_token(
    *,
    roles: list[str],
    sub: str = ACTOR_SUB,
    tenant_id: str | None = PLATFORM_TENANT,
    scopes: list[str] | None = None,
    exp_offset: int = 3600,
) -> str:
    now = int(time.time())
    payload: dict = {
        "sub": sub,
        "iat": now,
        "exp": now + exp_offset,
        "iss": TEST_ISSUER,
        "aud": TEST_AUDIENCE,
        "roles": roles,
        "scopes": scopes or [],
    }
    if tenant_id is not None:
        payload["tenant_id"] = tenant_id
    return jwt.encode(payload, TEST_SECRET, algorithm="HS256")


@pytest.fixture
def auth_config() -> AuthConfig:
    return AuthConfig(
        issuer=TEST_ISSUER,
        audience=TEST_AUDIENCE,
        verification_key=TEST_SECRET,
        algorithm="HS256",
        leeway_seconds=0,
        require_tenant=False,
        public_paths=("/api/tenants/health", "/health"),
    )


@pytest.fixture
def client(auth_config: AuthConfig) -> TestClient:
    app = create_app(
        enable_auth=True,
        auth_config=auth_config,
        rbac_matrix_path=RBAC_MATRIX,
    )
    return TestClient(app)


@pytest.fixture
def admin_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {make_token(roles=['PlatformAdmin'])}",
        "Idempotency-Key": "prov-test-key-0001",
        "Content-Type": "application/json",
    }


def _payload(**overrides) -> dict:
    body = {
        "slug": "acme-corp",
        "displayName": "Acme Corporation",
        "planCode": "enterprise",
        "dataResidency": "eu-west",
        "configuration": {
            "locale": "en-GB",
            "timezone": "Europe/London",
        },
        "metadata": {
            "industry": {"value": "manufacturing"},
            "salesforceAccountId": {"value": "SF-123"},
        },
    }
    body.update(overrides)
    return body


class TestSuccessfulProvisioning:
    def test_health_is_public(self, client: TestClient) -> None:
        response = client.get("/api/tenants/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_provisions_tenant_with_defaults(
        self, client: TestClient, admin_headers: dict[str, str]
    ) -> None:
        response = client.post(
            "/api/tenants", headers=admin_headers, json=_payload()
        )
        assert response.status_code == 201
        data = response.json()
        assert data["created"] is True
        assert data["slug"] == "acme-corp"
        assert data["displayName"] == "Acme Corporation"
        assert data["status"] == "active"
        assert data["planCode"] == "enterprise"
        assert data["dataResidency"] == "eu-west"
        assert UUID(data["tenantId"])
        assert data["configuration"]["locale"] == "en-GB"
        assert data["configuration"]["timezone"] == "Europe/London"
        assert data["configuration"]["schemaVersion"] == 1
        assert data["configuration"]["meteringEnabled"] is True
        assert data["configuration"]["gdprEnabled"] is True
        assert data["configuration"]["ccpaEnabled"] is True
        assert data["configuration"]["defaults"]["features"]["skills"] is True
        assert {m["key"] for m in data["metadata"]} == {
            "industry",
            "salesforceAccountId",
        }

        store = client.app.state.tenant_store
        tenant_id = UUID(data["tenantId"])
        assert store.get_tenant(tenant_id) is not None
        assert store.get_configuration(tenant_id) is not None
        assert len(store.get_metadata(tenant_id)) == 2


class TestIdempotency:
    def test_replay_returns_same_tenant(
        self, client: TestClient, admin_headers: dict[str, str]
    ) -> None:
        first = client.post("/api/tenants", headers=admin_headers, json=_payload())
        assert first.status_code == 201
        second = client.post("/api/tenants", headers=admin_headers, json=_payload())
        assert second.status_code == 200
        assert second.json()["tenantId"] == first.json()["tenantId"]
        assert second.json()["created"] is False
        # Only one tenant persisted
        assert len(client.app.state.tenant_store.list_tenants()) == 1

    def test_same_key_different_body_conflicts(
        self, client: TestClient, admin_headers: dict[str, str]
    ) -> None:
        assert (
            client.post(
                "/api/tenants", headers=admin_headers, json=_payload()
            ).status_code
            == 201
        )
        conflict = client.post(
            "/api/tenants",
            headers=admin_headers,
            json=_payload(displayName="Different Name"),
        )
        assert conflict.status_code == 409
        assert conflict.json()["detail"]["error"] == "idempotency_conflict"

    def test_missing_idempotency_key_rejected(
        self, client: TestClient
    ) -> None:
        headers = {
            "Authorization": f"Bearer {make_token(roles=['PlatformAdmin'])}",
            "Content-Type": "application/json",
        }
        response = client.post("/api/tenants", headers=headers, json=_payload())
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "idempotency_key_required"


class TestRbacEnforcement:
    def test_unauthenticated_returns_401(self, client: TestClient) -> None:
        response = client.post(
            "/api/tenants",
            headers={"Idempotency-Key": "prov-no-auth-0001"},
            json=_payload(),
        )
        assert response.status_code == 401
        body = response.json()
        assert body.get("error") == "token_missing" or (
            isinstance(body.get("detail"), dict)
            and body["detail"].get("error") == "unauthenticated"
        )

    def test_learner_forbidden(self, client: TestClient) -> None:
        headers = {
            "Authorization": f"Bearer {make_token(roles=['learner'])}",
            "Idempotency-Key": "prov-learner-0001",
            "Content-Type": "application/json",
        }
        response = client.post("/api/tenants", headers=headers, json=_payload())
        assert response.status_code == 403
        detail = response.json().get("detail") or response.json()
        assert isinstance(detail, dict)
        assert detail.get("error") == "forbidden"
        assert "PlatformAdmin" in detail.get("message", "")

    def test_tenant_admin_forbidden(self, client: TestClient) -> None:
        headers = {
            "Authorization": f"Bearer {make_token(roles=['tenant_admin'])}",
            "Idempotency-Key": "prov-tenant-admin-0001",
            "Content-Type": "application/json",
        }
        response = client.post(
            "/api/tenants",
            headers=headers,
            json=_payload(slug="other-co"),
        )
        assert response.status_code == 403
        detail = response.json()["detail"]
        assert detail["error"] == "forbidden"
        assert "PlatformAdmin" in detail["message"]

    def test_org_admin_forbidden(self, client: TestClient) -> None:
        headers = {
            "Authorization": f"Bearer {make_token(roles=['org_admin'])}",
            "Idempotency-Key": "prov-org-admin-0001",
            "Content-Type": "application/json",
        }
        response = client.post(
            "/api/tenants",
            headers=headers,
            json=_payload(slug="org-admin-co"),
        )
        assert response.status_code == 403

    def test_platform_admin_snake_case_allowed(
        self, client: TestClient
    ) -> None:
        headers = {
            "Authorization": f"Bearer {make_token(roles=['platform_admin'])}",
            "Idempotency-Key": "prov-snake-admin-0001",
            "Content-Type": "application/json",
        }
        response = client.post(
            "/api/tenants",
            headers=headers,
            json=_payload(slug="snake-admin-co"),
        )
        assert response.status_code == 201

    def test_platform_admin_pascal_case_allowed(
        self, client: TestClient, admin_headers: dict[str, str]
    ) -> None:
        response = client.post(
            "/api/tenants",
            headers={**admin_headers, "Idempotency-Key": "prov-pascal-admin-0001"},
            json=_payload(slug="pascal-admin-co"),
        )
        assert response.status_code == 201

    def test_auth_middleware_mounted_by_default(
        self, auth_config: AuthConfig
    ) -> None:
        """create_app() enables Story S2 middleware unless explicitly disabled."""
        app = create_app(
            auth_config=auth_config,
            rbac_matrix_path=RBAC_MATRIX,
        )
        default_client = TestClient(app)
        response = default_client.post(
            "/api/tenants",
            headers={"Idempotency-Key": "prov-default-auth-0001"},
            json=_payload(slug="default-auth-co"),
        )
        assert response.status_code == 401

    def test_route_gate_fail_closed_without_middleware(self) -> None:
        """Even if middleware is off, missing principal yields 401 (not open)."""
        app = create_app(enable_auth=False)
        open_client = TestClient(app)
        response = open_client.post(
            "/api/tenants",
            headers={"Idempotency-Key": "prov-fail-closed-0001"},
            json=_payload(slug="fail-closed-co"),
        )
        assert response.status_code == 401
        assert response.json()["detail"]["error"] == "unauthenticated"


class TestTenantIsolationAndEvents:
    def test_database_isolation_across_tenants(
        self, client: TestClient, admin_headers: dict[str, str]
    ) -> None:
        first = client.post(
            "/api/tenants",
            headers=admin_headers,
            json=_payload(slug="tenant-alpha"),
        )
        assert first.status_code == 201
        headers_b = {
            **admin_headers,
            "Idempotency-Key": "prov-test-key-0002",
        }
        second = client.post(
            "/api/tenants",
            headers=headers_b,
            json=_payload(slug="tenant-beta", displayName="Beta"),
        )
        assert second.status_code == 201

        store = client.app.state.tenant_store
        alpha_id = UUID(first.json()["tenantId"])
        beta_id = UUID(second.json()["tenantId"])

        alpha_view = store.tenants_for_isolation_check(alpha_id)
        beta_view = store.tenants_for_isolation_check(beta_id)

        assert alpha_view["tenant"].slug == "tenant-alpha"
        assert beta_view["tenant"].slug == "tenant-beta"
        assert str(beta_id) in alpha_view["foreign_tenant_ids"]
        assert str(alpha_id) in beta_view["foreign_tenant_ids"]
        # Configuration and metadata are strictly tenant-scoped
        assert alpha_view["configuration"].tenant_id == alpha_id
        assert all(m.tenant_id == alpha_id for m in alpha_view["metadata"])
        assert beta_view["configuration"].tenant_id == beta_id
        assert all(m.tenant_id == beta_id for m in beta_view["metadata"])

    def test_event_emitted_once_and_tenant_scoped(
        self, client: TestClient, admin_headers: dict[str, str]
    ) -> None:
        first = client.post(
            "/api/tenants",
            headers=admin_headers,
            json=_payload(slug="eventful-co"),
        )
        assert first.status_code == 201
        tenant_id = first.json()["tenantId"]

        bus = client.app.state.event_bus
        assert len(bus.messages) == 1
        message = bus.messages[0]
        assert message["channel"] == EVENT_CHANNEL
        assert message["partition_key"] == tenant_id
        event = message["event"]
        assert event["type"] == EVENT_TYPE
        assert event["tenantId"] == tenant_id
        assert event["data"]["tenantId"] == tenant_id
        assert event["subject"] == f"tenant/{tenant_id}"
        assert event["data"]["requestingTenantId"] == PLATFORM_TENANT
        assert event["data"]["idempotencyKey"] == admin_headers["Idempotency-Key"]

        # Idempotent replay must not emit a second event
        replay = client.post(
            "/api/tenants",
            headers=admin_headers,
            json=_payload(slug="eventful-co"),
        )
        assert replay.status_code == 200
        assert len(bus.messages) == 1
        assert len(bus.events_for_tenant(tenant_id)) == 1

    def test_invalid_payload_rejected(
        self, client: TestClient, admin_headers: dict[str, str]
    ) -> None:
        response = client.post(
            "/api/tenants",
            headers=admin_headers,
            json={"slug": "BAD SLUG", "displayName": "X"},
        )
        assert response.status_code == 422
