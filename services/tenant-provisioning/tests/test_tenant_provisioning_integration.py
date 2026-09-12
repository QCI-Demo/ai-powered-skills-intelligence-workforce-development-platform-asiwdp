"""Integration tests for tenant provisioning.

Verifies successful provisioning, idempotency, RBAC enforcement across token
scopes/roles, in-memory database isolation, and provisioning event emission.
"""

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
    permissions: list[str] | None = None,
    exp_offset: int = 3600,
) -> str:
    """Mint an HS256 JWT for provisioning calls with the given roles/scopes."""
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
    if permissions is not None:
        payload["permissions"] = permissions
    return jwt.encode(payload, TEST_SECRET, algorithm="HS256")


def auth_headers(
    *,
    roles: list[str],
    idempotency_key: str,
    scopes: list[str] | None = None,
    permissions: list[str] | None = None,
    tenant_id: str | None = PLATFORM_TENANT,
) -> dict[str, str]:
    return {
        "Authorization": (
            f"Bearer {make_token(roles=roles, scopes=scopes, permissions=permissions, tenant_id=tenant_id)}"
        ),
        "Idempotency-Key": idempotency_key,
        "Content-Type": "application/json",
    }


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
    """Spin up the provisioning app with in-memory DB + event bus."""
    app = create_app(
        enable_auth=True,
        auth_config=auth_config,
        rbac_matrix_path=RBAC_MATRIX,
    )
    # Fresh store/bus per test client
    assert hasattr(app.state, "tenant_store")
    assert hasattr(app.state, "event_bus")
    return TestClient(app)


@pytest.fixture
def admin_headers() -> dict[str, str]:
    return auth_headers(
        roles=["PlatformAdmin"],
        scopes=["tenants:admin"],
        idempotency_key="prov-test-key-0001",
    )


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

        # In-memory DB holds tenant-scoped rows
        store = client.app.state.tenant_store
        tenant_id = UUID(data["tenantId"])
        assert store.get_tenant(tenant_id) is not None
        assert store.get_configuration(tenant_id) is not None
        assert len(store.get_metadata(tenant_id)) == 2

    def test_minimal_payload_seeds_platform_defaults(
        self, client: TestClient
    ) -> None:
        headers = auth_headers(
            roles=["PlatformAdmin"],
            scopes=["tenants:admin"],
            idempotency_key="prov-minimal-0001",
        )
        response = client.post(
            "/api/tenants",
            headers=headers,
            json={"slug": "minimal-co", "displayName": "Minimal Co"},
        )
        assert response.status_code == 201
        cfg = response.json()["configuration"]
        assert cfg["locale"] == "en-US"
        assert cfg["timezone"] == "UTC"
        assert cfg["meteringEnabled"] is True
        assert cfg["gdprEnabled"] is True
        assert cfg["ccpaEnabled"] is True


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

    def test_missing_idempotency_key_rejected(self, client: TestClient) -> None:
        headers = {
            "Authorization": f"Bearer {make_token(roles=['PlatformAdmin'])}",
            "Content-Type": "application/json",
        }
        response = client.post("/api/tenants", headers=headers, json=_payload())
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "idempotency_key_required"

    def test_distinct_keys_create_distinct_tenants(
        self, client: TestClient
    ) -> None:
        a = client.post(
            "/api/tenants",
            headers=auth_headers(
                roles=["PlatformAdmin"],
                idempotency_key="prov-distinct-a-0001",
            ),
            json=_payload(slug="distinct-a"),
        )
        b = client.post(
            "/api/tenants",
            headers=auth_headers(
                roles=["PlatformAdmin"],
                idempotency_key="prov-distinct-b-0001",
            ),
            json=_payload(slug="distinct-b"),
        )
        assert a.status_code == 201 and b.status_code == 201
        assert a.json()["tenantId"] != b.json()["tenantId"]
        assert len(client.app.state.tenant_store.list_tenants()) == 2


class TestRbacEnforcement:
    """Provision with various token roles/scopes; only PlatformAdmin succeeds."""

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

    @pytest.mark.parametrize(
        ("roles", "scopes", "key_suffix"),
        [
            (["learner"], ["skills:read"], "learner"),
            (["tenant_admin"], ["tenants:write", "tenants:admin"], "tenant-admin"),
            (["org_admin"], ["organizations:write"], "org-admin"),
            (["skills_manager"], ["skills:admin"], "skills-mgr"),
            (["service_account"], ["tenants:admin"], "svc-acct"),
            # Elevated tenant scopes alone are insufficient without PlatformAdmin
            (["learner"], ["tenants:admin", "*"], "learner-admin-scope"),
            ([], ["tenants:admin"], "scopes-only"),
        ],
    )
    def test_non_platform_admin_scopes_forbidden(
        self,
        client: TestClient,
        roles: list[str],
        scopes: list[str],
        key_suffix: str,
    ) -> None:
        headers = auth_headers(
            roles=roles,
            scopes=scopes,
            idempotency_key=f"prov-rbac-{key_suffix}-0001",
        )
        response = client.post(
            "/api/tenants",
            headers=headers,
            json=_payload(slug=f"rbac-{key_suffix}"),
        )
        assert response.status_code == 403
        detail = response.json().get("detail") or response.json()
        assert isinstance(detail, dict)
        assert detail.get("error") == "forbidden"
        assert "PlatformAdmin" in detail.get("message", "")

    def test_platform_admin_snake_case_allowed(self, client: TestClient) -> None:
        headers = auth_headers(
            roles=["platform_admin"],
            scopes=["tenants:admin"],
            idempotency_key="prov-snake-admin-0001",
        )
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

    def test_platform_admin_without_scopes_allowed(
        self, client: TestClient
    ) -> None:
        """Role gate is authoritative; empty scopes still provision."""
        headers = auth_headers(
            roles=["PlatformAdmin"],
            scopes=[],
            idempotency_key="prov-admin-no-scope-0001",
        )
        response = client.post(
            "/api/tenants",
            headers=headers,
            json=_payload(slug="admin-no-scope-co"),
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
            json=_payload(
                slug="tenant-alpha",
                metadata={"region": {"value": "alpha-only"}},
            ),
        )
        assert first.status_code == 201
        headers_b = {
            **admin_headers,
            "Idempotency-Key": "prov-test-key-0002",
        }
        second = client.post(
            "/api/tenants",
            headers=headers_b,
            json=_payload(
                slug="tenant-beta",
                displayName="Beta",
                metadata={"region": {"value": "beta-only"}},
            ),
        )
        assert second.status_code == 201

        store = client.app.state.tenant_store
        alpha_id = UUID(first.json()["tenantId"])
        beta_id = UUID(second.json()["tenantId"])
        assert alpha_id != beta_id

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

        alpha_meta = {m.meta_key: m.meta_value for m in alpha_view["metadata"]}
        beta_meta = {m.meta_key: m.meta_value for m in beta_view["metadata"]}
        assert alpha_meta["region"]["value"] == "alpha-only"
        assert beta_meta["region"]["value"] == "beta-only"
        # Cross-tenant lookup never returns the other tenant's rows
        assert store.get_configuration(alpha_id).tenant_id == alpha_id
        assert store.get_tenant(beta_id).slug == "tenant-beta"
        assert all(m.tenant_id == alpha_id for m in store.get_metadata(alpha_id))
        assert all(m.tenant_id == beta_id for m in store.get_metadata(beta_id))

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
        assert event["time"]
        assert event["data"]["timestamp"]
        assert event["data"]["timestamp"] == event["data"]["provisionedAt"]
        assert event["data"]["configuration"]["schemaVersion"] == 1
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

    def test_events_partitioned_per_tenant(self, client: TestClient) -> None:
        """Each provisioned tenant gets its own partitioned telemetry event."""
        for slug, key in (
            ("event-alpha", "prov-event-alpha-0001"),
            ("event-beta", "prov-event-beta-0001"),
        ):
            response = client.post(
                "/api/tenants",
                headers=auth_headers(
                    roles=["PlatformAdmin"],
                    scopes=["tenants:admin"],
                    idempotency_key=key,
                ),
                json=_payload(slug=slug),
            )
            assert response.status_code == 201

        bus = client.app.state.event_bus
        assert len(bus.messages) == 2
        partition_keys = {m["partition_key"] for m in bus.messages}
        tenant_ids = {m["event"]["tenantId"] for m in bus.messages}
        assert partition_keys == tenant_ids
        assert len(partition_keys) == 2
        for message in bus.messages:
            tid = message["event"]["tenantId"]
            assert message["partition_key"] == tid
            assert message["event"]["data"]["tenantId"] == tid
            assert len(bus.events_for_tenant(tid)) == 1

    def test_invalid_payload_rejected(
        self, client: TestClient, admin_headers: dict[str, str]
    ) -> None:
        response = client.post(
            "/api/tenants",
            headers=admin_headers,
            json={"slug": "BAD SLUG", "displayName": "X"},
        )
        assert response.status_code == 422
