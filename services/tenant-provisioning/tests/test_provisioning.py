"""Integration tests for tenant provisioning API endpoints."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from starlette.testclient import TestClient

from tests.conftest import (
    LEARNER_ID,
    PLATFORM_ADMIN_ID,
    TENANT_ADMIN_ID,
    TEST_TENANT_ID,
    make_token,
)

if TYPE_CHECKING:
    from tenant_provisioning.events import InMemoryEventPublisher


class TestHealthEndpoint:
    """Tests for unauthenticated health endpoint."""

    def test_health_returns_200_without_auth(self, client: TestClient) -> None:
        """Health endpoint should be accessible without authentication."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        assert response.json()["service"] == "tenant-provisioning"


class TestCreateTenantRBAC:
    """Tests for RBAC enforcement on tenant creation."""

    def test_create_tenant_requires_authentication(self, client: TestClient) -> None:
        """Creating a tenant requires valid authentication."""
        response = client.post(
            "/api/tenants",
            json={
                "name": "Test Corp",
                "slug": "test-corp",
                "contactEmail": "admin@test.com",
            },
        )
        assert response.status_code == 401
        assert response.json()["error"] == "token_missing"

    def test_create_tenant_denied_for_learner(
        self, client: TestClient, learner_token: str
    ) -> None:
        """Learners should not be able to create tenants."""
        response = client.post(
            "/api/tenants",
            headers={"Authorization": f"Bearer {learner_token}"},
            json={
                "name": "Test Corp",
                "slug": "test-corp",
                "contactEmail": "admin@test.com",
            },
        )
        assert response.status_code == 403
        assert response.json()["error"] == "forbidden"

    def test_create_tenant_denied_for_tenant_admin(
        self, client: TestClient, tenant_admin_token: str
    ) -> None:
        """Tenant admins should not be able to create new tenants."""
        response = client.post(
            "/api/tenants",
            headers={"Authorization": f"Bearer {tenant_admin_token}"},
            json={
                "name": "Another Corp",
                "slug": "another-corp",
                "contactEmail": "admin@another.com",
            },
        )
        assert response.status_code == 403
        assert response.json()["error"] == "forbidden"

    def test_create_tenant_allowed_for_platform_admin(
        self, client: TestClient, platform_admin_token: str
    ) -> None:
        """Platform admins should be able to create tenants."""
        response = client.post(
            "/api/tenants",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
            json={
                "name": "Acme Corporation",
                "slug": "acme-corp",
                "contactEmail": "admin@acme.com",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Acme Corporation"
        assert data["slug"] == "acme-corp"
        assert data["status"] == "active"
        assert data["tier"] == "standard"
        assert "id" in data
        assert "X-Tenant-Id" in response.headers


class TestCreateTenantValidation:
    """Tests for request validation on tenant creation."""

    def test_create_tenant_validates_required_fields(
        self, client: TestClient, platform_admin_token: str
    ) -> None:
        """Missing required fields should return validation error."""
        response = client.post(
            "/api/tenants",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
            json={"name": "Test"},  # Missing slug and contactEmail
        )
        assert response.status_code == 400
        assert response.json()["error"] == "validation_error"

    def test_create_tenant_validates_slug_format(
        self, client: TestClient, platform_admin_token: str
    ) -> None:
        """Invalid slug format should be rejected."""
        response = client.post(
            "/api/tenants",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
            json={
                "name": "Test Corp",
                "slug": "Invalid Slug!",  # Invalid characters
                "contactEmail": "admin@test.com",
            },
        )
        assert response.status_code == 400
        assert response.json()["error"] == "validation_error"

    def test_create_tenant_validates_email_format(
        self, client: TestClient, platform_admin_token: str
    ) -> None:
        """Invalid email format should be rejected."""
        response = client.post(
            "/api/tenants",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
            json={
                "name": "Test Corp",
                "slug": "test-corp",
                "contactEmail": "not-an-email",
            },
        )
        assert response.status_code == 400
        assert response.json()["error"] == "validation_error"

    def test_create_tenant_rejects_reserved_slugs(
        self, client: TestClient, platform_admin_token: str
    ) -> None:
        """Reserved slugs should be rejected."""
        response = client.post(
            "/api/tenants",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
            json={
                "name": "Admin Corp",
                "slug": "admin",  # Reserved slug
                "contactEmail": "admin@admin.com",
            },
        )
        assert response.status_code == 400
        assert "reserved" in response.json()["message"].lower()


class TestCreateTenantSuccess:
    """Tests for successful tenant creation."""

    def test_create_tenant_with_default_tier(
        self, client: TestClient, platform_admin_token: str
    ) -> None:
        """Creating tenant without tier should default to standard."""
        response = client.post(
            "/api/tenants",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
            json={
                "name": "Default Tier Corp",
                "slug": "default-tier",
                "contactEmail": "admin@default.com",
            },
        )
        assert response.status_code == 201
        assert response.json()["tier"] == "standard"

    def test_create_tenant_with_enterprise_tier(
        self, client: TestClient, platform_admin_token: str
    ) -> None:
        """Creating enterprise tenant should have enterprise configuration."""
        response = client.post(
            "/api/tenants",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
            json={
                "name": "Enterprise Corp",
                "slug": "enterprise-corp",
                "contactEmail": "admin@enterprise.com",
                "tier": "enterprise",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["tier"] == "enterprise"
        # Enterprise tier should have unlimited users
        assert data["configuration"]["limits"]["maxUsers"] == -1

    def test_create_tenant_with_free_tier(
        self, client: TestClient, platform_admin_token: str
    ) -> None:
        """Creating free tenant should have limited configuration."""
        response = client.post(
            "/api/tenants",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
            json={
                "name": "Free Tier Corp",
                "slug": "free-tier",
                "contactEmail": "admin@free.com",
                "tier": "free",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["tier"] == "free"
        # Free tier should have limited users
        assert data["configuration"]["limits"]["maxUsers"] == 10
        # Free tier should not have analytics
        assert data["configuration"]["features"]["analytics"] is False

    def test_create_tenant_with_metadata(
        self, client: TestClient, platform_admin_token: str
    ) -> None:
        """Creating tenant with custom metadata should preserve it."""
        metadata = {"industry": "technology", "size": "startup"}
        response = client.post(
            "/api/tenants",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
            json={
                "name": "Meta Corp",
                "slug": "meta-corp",
                "contactEmail": "admin@meta.com",
                "metadata": metadata,
            },
        )
        assert response.status_code == 201
        assert response.json()["metadata"] == metadata


class TestIdempotency:
    """Tests for idempotency key handling."""

    def test_idempotent_create_returns_same_response(
        self, client: TestClient, platform_admin_token: str
    ) -> None:
        """Repeated requests with same idempotency key return same response."""
        idempotency_key = str(uuid.uuid4())
        payload = {
            "name": "Idempotent Corp",
            "slug": "idempotent-corp",
            "contactEmail": "admin@idempotent.com",
        }

        # First request
        response1 = client.post(
            "/api/tenants",
            headers={
                "Authorization": f"Bearer {platform_admin_token}",
                "Idempotency-Key": idempotency_key,
            },
            json=payload,
        )
        assert response1.status_code == 201
        tenant_id1 = response1.json()["id"]

        # Second request with same key
        response2 = client.post(
            "/api/tenants",
            headers={
                "Authorization": f"Bearer {platform_admin_token}",
                "Idempotency-Key": idempotency_key,
            },
            json=payload,
        )
        assert response2.status_code == 201
        tenant_id2 = response2.json()["id"]

        # Should return the same tenant
        assert tenant_id1 == tenant_id2

    def test_idempotency_conflict_with_different_payload(
        self, client: TestClient, platform_admin_token: str
    ) -> None:
        """Reusing idempotency key with different payload returns error."""
        idempotency_key = str(uuid.uuid4())

        # First request
        response1 = client.post(
            "/api/tenants",
            headers={
                "Authorization": f"Bearer {platform_admin_token}",
                "Idempotency-Key": idempotency_key,
            },
            json={
                "name": "First Corp",
                "slug": "first-corp",
                "contactEmail": "admin@first.com",
            },
        )
        assert response1.status_code == 201

        # Second request with different payload
        response2 = client.post(
            "/api/tenants",
            headers={
                "Authorization": f"Bearer {platform_admin_token}",
                "Idempotency-Key": idempotency_key,
            },
            json={
                "name": "Different Corp",
                "slug": "different-corp",
                "contactEmail": "admin@different.com",
            },
        )
        assert response2.status_code == 422
        assert response2.json()["error"] == "idempotency_conflict"


class TestTenantIsolation:
    """Tests for tenant data isolation."""

    def test_duplicate_slug_rejected(
        self, client: TestClient, platform_admin_token: str
    ) -> None:
        """Creating tenant with existing slug should fail."""
        payload = {
            "name": "Unique Corp",
            "slug": "unique-corp",
            "contactEmail": "admin@unique.com",
        }

        # First creation should succeed
        response1 = client.post(
            "/api/tenants",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
            json=payload,
        )
        assert response1.status_code == 201

        # Second creation with same slug should fail
        response2 = client.post(
            "/api/tenants",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
            json=payload,
        )
        assert response2.status_code == 409
        assert response2.json()["error"] == "conflict"


class TestGetTenant:
    """Tests for get tenant endpoint."""

    def test_get_tenant_by_id(
        self, client: TestClient, platform_admin_token: str
    ) -> None:
        """Platform admin can retrieve tenant by ID."""
        # Create tenant first
        create_response = client.post(
            "/api/tenants",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
            json={
                "name": "Retrievable Corp",
                "slug": "retrievable-corp",
                "contactEmail": "admin@retrievable.com",
            },
        )
        assert create_response.status_code == 201
        tenant_id = create_response.json()["id"]

        # Retrieve tenant
        get_response = client.get(
            f"/api/tenants/{tenant_id}",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
        )
        assert get_response.status_code == 200
        assert get_response.json()["id"] == tenant_id
        assert get_response.json()["slug"] == "retrievable-corp"

    def test_get_tenant_not_found(
        self, client: TestClient, platform_admin_token: str
    ) -> None:
        """Getting non-existent tenant returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.get(
            f"/api/tenants/{fake_id}",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
        )
        assert response.status_code == 404
        assert response.json()["error"] == "not_found"

    def test_get_tenant_invalid_id(
        self, client: TestClient, platform_admin_token: str
    ) -> None:
        """Getting tenant with invalid ID format returns 400."""
        response = client.get(
            "/api/tenants/not-a-uuid",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
        )
        assert response.status_code == 400
        assert response.json()["error"] == "invalid_parameter"


class TestEventEmission:
    """Tests for provisioning event emission."""

    def test_provisioning_emits_events(
        self,
        client: TestClient,
        platform_admin_token: str,
        event_publisher: "InMemoryEventPublisher",
    ) -> None:
        """Tenant provisioning should emit appropriate events."""
        event_publisher.clear()

        response = client.post(
            "/api/tenants",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
            json={
                "name": "Event Corp",
                "slug": "event-corp",
                "contactEmail": "admin@event.com",
            },
        )
        assert response.status_code == 201
        tenant_id = uuid.UUID(response.json()["id"])

        # Check events were emitted
        events = event_publisher.get_events_for_tenant(tenant_id)
        event_types = [e.event_type for e in events]

        assert "tenant.provisioning.started" in event_types
        assert "tenant.provisioned" in event_types

    def test_event_contains_tenant_metadata(
        self,
        client: TestClient,
        platform_admin_token: str,
        event_publisher: "InMemoryEventPublisher",
    ) -> None:
        """Provisioning events should contain tenant metadata."""
        event_publisher.clear()

        response = client.post(
            "/api/tenants",
            headers={"Authorization": f"Bearer {platform_admin_token}"},
            json={
                "name": "Metadata Event Corp",
                "slug": "metadata-event-corp",
                "contactEmail": "admin@metadata-event.com",
                "tier": "enterprise",
            },
        )
        assert response.status_code == 201
        tenant_id = uuid.UUID(response.json()["id"])

        # Find the provisioned event
        events = event_publisher.get_events_for_tenant(tenant_id)
        provisioned_event = next(
            (e for e in events if e.event_type == "tenant.provisioned"),
            None,
        )

        assert provisioned_event is not None
        assert provisioned_event.payload["slug"] == "metadata-event-corp"
        assert provisioned_event.payload["tier"] == "enterprise"
        assert provisioned_event.payload["name"] == "Metadata Event Corp"
