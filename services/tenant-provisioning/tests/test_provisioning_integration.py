"""Integration tests for automated tenant provisioning."""

from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient

from asiwdp_tenant_provisioning.events import EVENT_TYPE, InMemoryEventBus
from asiwdp_tenant_provisioning.repository import TenantRepository

from .helpers import make_token

VALID_PAYLOAD = {
    "slug": "acme-corp",
    "display_name": "Acme Corporation",
    "plan_code": "enterprise",
    "region": "us-east-1",
    "timezone": "America/New_York",
    "contact": {"billing_email": "billing@acme.example"},
    "metadata": {"industry": {"code": "tech"}, "seats": {"value": 500}},
}


def test_health_is_public(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "up"


def test_provision_requires_auth(client: TestClient) -> None:
    response = client.post("/api/tenants", json=VALID_PAYLOAD)
    assert response.status_code == 401
    assert response.json()["error"] in {"token_missing", "unauthenticated"}


def test_provision_rejects_non_platform_admin(client: TestClient) -> None:
    token = make_token(roles=["tenant_admin"], scopes=["tenants:admin"])
    response = client.post(
        "/api/tenants",
        json=VALID_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    body = response.json()
    assert body["error"] == "forbidden"
    assert "PlatformAdmin" in body["message"]


def test_provision_rejects_learner(client: TestClient) -> None:
    token = make_token(roles=["learner"], scopes=["skills:read"])
    response = client.post(
        "/api/tenants",
        json=VALID_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_successful_provisioning_seeds_defaults_and_emits_event(
    client: TestClient,
    repository: TenantRepository,
    event_bus: InMemoryEventBus,
    platform_admin_headers: dict[str, str],
) -> None:
    response = client.post(
        "/api/tenants",
        json=VALID_PAYLOAD,
        headers={
            **platform_admin_headers,
            "Idempotency-Key": "prov-acme-001",
            "X-Correlation-Id": "corr-test-1",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["slug"] == "acme-corp"
    assert body["display_name"] == "Acme Corporation"
    assert body["status"] == "active"
    assert body["idempotent_replay"] is False
    tenant_id = UUID(body["tenant_id"])

    config_keys = {item["config_key"] for item in body["configuration"]}
    assert "locale" in config_keys
    assert "privacy.consent_required" in config_keys
    assert "features.skills_framework" in config_keys
    locale = next(c for c in body["configuration"] if c["config_key"] == "locale")
    assert locale["config_value"] == "en-US"
    assert locale["is_default"] is True

    meta_keys = {item["meta_key"] for item in body["metadata"]}
    assert "industry" in meta_keys
    assert "seats" in meta_keys

    # Persistence isolation: configs/metadata only for this tenant_id
    stored_configs = repository.list_configuration(tenant_id)
    assert all(c.tenant_id == tenant_id for c in stored_configs)
    assert len(stored_configs) == len(body["configuration"])

    stored_meta = repository.list_metadata(tenant_id)
    assert all(m.tenant_id == tenant_id for m in stored_meta)

    # Event emission
    assert len(event_bus.events) == 1
    event = event_bus.events[0]
    assert event.event_type == EVENT_TYPE
    assert event.tenant_id == str(tenant_id)
    assert event.partition_key == str(tenant_id)
    assert event.correlation_id == "corr-test-1"
    assert event.payload["slug"] == "acme-corp"
    assert event.payload["replay"] is False
    assert "locale" in event.payload["default_config_keys"]
    assert event.actor["roles"] == ["PlatformAdmin"]


def test_platform_admin_snake_case_role_accepted(
    client: TestClient,
    platform_admin_snake_headers: dict[str, str],
) -> None:
    response = client.post(
        "/api/tenants",
        json={**VALID_PAYLOAD, "slug": "beta-co"},
        headers=platform_admin_snake_headers,
    )
    assert response.status_code == 201
    assert response.json()["slug"] == "beta-co"


def test_idempotency_returns_same_tenant_without_duplicate_event(
    client: TestClient,
    event_bus: InMemoryEventBus,
    platform_admin_headers: dict[str, str],
) -> None:
    headers = {
        **platform_admin_headers,
        "Idempotency-Key": "idem-stable-1",
    }
    first = client.post("/api/tenants", json=VALID_PAYLOAD, headers=headers)
    assert first.status_code == 201
    first_body = first.json()

    second = client.post("/api/tenants", json=VALID_PAYLOAD, headers=headers)
    assert second.status_code == 200
    second_body = second.json()

    assert second_body["tenant_id"] == first_body["tenant_id"]
    assert second_body["idempotent_replay"] is True
    assert len(event_bus.events) == 1  # no re-publish on replay


def test_idempotency_conflict_on_different_payload(
    client: TestClient,
    platform_admin_headers: dict[str, str],
) -> None:
    headers = {
        **platform_admin_headers,
        "Idempotency-Key": "idem-conflict-1",
    }
    first = client.post("/api/tenants", json=VALID_PAYLOAD, headers=headers)
    assert first.status_code == 201

    conflict = client.post(
        "/api/tenants",
        json={**VALID_PAYLOAD, "display_name": "Different Name"},
        headers=headers,
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"] == "conflict"


def test_duplicate_slug_without_idempotency_key_conflicts(
    client: TestClient,
    platform_admin_headers: dict[str, str],
) -> None:
    first = client.post(
        "/api/tenants",
        json=VALID_PAYLOAD,
        headers=platform_admin_headers,
    )
    assert first.status_code == 201

    second = client.post(
        "/api/tenants",
        json=VALID_PAYLOAD,
        headers=platform_admin_headers,
    )
    assert second.status_code == 409


def test_payload_validation_rejects_invalid_slug(
    client: TestClient,
    platform_admin_headers: dict[str, str],
) -> None:
    response = client.post(
        "/api/tenants",
        json={**VALID_PAYLOAD, "slug": "INVALID SLUG!"},
        headers=platform_admin_headers,
    )
    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


def test_tenant_data_isolation_across_tenants(
    client: TestClient,
    repository: TenantRepository,
    event_bus: InMemoryEventBus,
    platform_admin_headers: dict[str, str],
) -> None:
    r1 = client.post(
        "/api/tenants",
        json={**VALID_PAYLOAD, "slug": "tenant-alpha", "display_name": "Alpha"},
        headers=platform_admin_headers,
    )
    r2 = client.post(
        "/api/tenants",
        json={**VALID_PAYLOAD, "slug": "tenant-beta", "display_name": "Beta"},
        headers=platform_admin_headers,
    )
    assert r1.status_code == 201
    assert r2.status_code == 201

    tid1 = UUID(r1.json()["tenant_id"])
    tid2 = UUID(r2.json()["tenant_id"])
    assert tid1 != tid2

    alpha_configs = repository.list_configuration(tid1)
    beta_configs = repository.list_configuration(tid2)
    assert alpha_configs and beta_configs
    assert {c.tenant_id for c in alpha_configs} == {tid1}
    assert {c.tenant_id for c in beta_configs} == {tid2}

    alpha_events = event_bus.events_for_tenant(tid1)
    beta_events = event_bus.events_for_tenant(tid2)
    assert len(alpha_events) == 1
    assert len(beta_events) == 1
    assert alpha_events[0].tenant_id != beta_events[0].tenant_id
