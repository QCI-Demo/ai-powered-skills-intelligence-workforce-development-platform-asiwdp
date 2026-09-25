"""Integration tests for tenant provisioning service.

Tests cover:
- Successful tenant provisioning
- Idempotency behavior
- RBAC enforcement (PlatformAdmin required)
- Tenant data isolation
- Event emission
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from conftest import (
    MockPrincipal,
    TestEventPublisher,
    inject_principal,
)
from src.controllers.tenant_controller import (
    InMemoryIdempotencyStore,
    InMemoryTenantRepository,
)


class TestTenantProvisioning:
    """Tests for POST /api/tenants endpoint."""

    def test_successful_provisioning(
        self,
        client: TestClient,
        platform_admin_principal: MockPrincipal,
        event_publisher: TestEventPublisher,
    ):
        """Test successful tenant creation with valid request."""
        inject_principal(client, platform_admin_principal)

        response = client.post(
            "/api/tenants",
            json={
                "name": "Acme Corporation",
                "slug": "acme-corp",
                "display_name": "Acme Corp",
                "tier": "professional",
                "contact_email": "admin@acme.example.com",
                "metadata": {"industry": "technology"},
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["message"] == "Tenant provisioned successfully"
        assert data["idempotent"] is False
        assert data["tenant"]["name"] == "Acme Corporation"
        assert data["tenant"]["slug"] == "acme-corp"
        assert data["tenant"]["tier"] == "professional"
        assert data["tenant"]["status"] == "active"
        assert "tenant_id" in data["tenant"]

        # Verify events emitted
        assert len(event_publisher.events) >= 2
        event_types = [e["type"] for e in event_publisher.events]
        assert "tenant.provisioning.started" in event_types
        assert "tenant.provisioning.completed" in event_types

    def test_provisioning_with_defaults(
        self,
        client: TestClient,
        platform_admin_principal: MockPrincipal,
    ):
        """Test that provisioning applies default tier (standard)."""
        inject_principal(client, platform_admin_principal)

        response = client.post(
            "/api/tenants",
            json={
                "name": "Default Tier Corp",
                "slug": "default-tier",
                "contact_email": "admin@default.example.com",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["tenant"]["tier"] == "standard"

    def test_duplicate_name_rejected(
        self,
        client: TestClient,
        platform_admin_principal: MockPrincipal,
        tenant_repository: InMemoryTenantRepository,
    ):
        """Test that duplicate tenant names are rejected."""
        inject_principal(client, platform_admin_principal)

        # Create first tenant
        response1 = client.post(
            "/api/tenants",
            json={
                "name": "Duplicate Corp",
                "slug": "duplicate-1",
                "contact_email": "admin@dup1.example.com",
            },
        )
        assert response1.status_code == 201

        # Attempt duplicate
        response2 = client.post(
            "/api/tenants",
            json={
                "name": "Duplicate Corp",
                "slug": "duplicate-2",
                "contact_email": "admin@dup2.example.com",
            },
        )
        assert response2.status_code == 409
        assert response2.json()["error"] == "tenant_exists"

    def test_duplicate_slug_rejected(
        self,
        client: TestClient,
        platform_admin_principal: MockPrincipal,
    ):
        """Test that duplicate tenant slugs are rejected."""
        inject_principal(client, platform_admin_principal)

        # Create first tenant
        response1 = client.post(
            "/api/tenants",
            json={
                "name": "First Corp",
                "slug": "same-slug",
                "contact_email": "admin@first.example.com",
            },
        )
        assert response1.status_code == 201

        # Attempt with same slug
        response2 = client.post(
            "/api/tenants",
            json={
                "name": "Second Corp",
                "slug": "same-slug",
                "contact_email": "admin@second.example.com",
            },
        )
        assert response2.status_code == 409
        assert "slug" in response2.json()["message"].lower()


class TestIdempotency:
    """Tests for idempotency key handling."""

    def test_idempotent_request_returns_cached_response(
        self,
        client: TestClient,
        platform_admin_principal: MockPrincipal,
    ):
        """Test that same idempotency key returns same response."""
        inject_principal(client, platform_admin_principal)
        idempotency_key = f"idem-{uuid4()}"

        # First request
        response1 = client.post(
            "/api/tenants",
            headers={"Idempotency-Key": idempotency_key},
            json={
                "name": "Idempotent Corp",
                "slug": "idempotent-corp",
                "contact_email": "admin@idem.example.com",
            },
        )
        assert response1.status_code == 201
        tenant_id1 = response1.json()["tenant"]["tenant_id"]

        # Second request with same key and body
        response2 = client.post(
            "/api/tenants",
            headers={"Idempotency-Key": idempotency_key},
            json={
                "name": "Idempotent Corp",
                "slug": "idempotent-corp",
                "contact_email": "admin@idem.example.com",
            },
        )
        assert response2.status_code == 201
        data2 = response2.json()
        assert data2["idempotent"] is True
        assert data2["tenant"]["tenant_id"] == tenant_id1

    def test_idempotency_key_with_different_body_rejected(
        self,
        client: TestClient,
        platform_admin_principal: MockPrincipal,
    ):
        """Test that reusing idempotency key with different body fails."""
        inject_principal(client, platform_admin_principal)
        idempotency_key = f"idem-{uuid4()}"

        # First request
        response1 = client.post(
            "/api/tenants",
            headers={"Idempotency-Key": idempotency_key},
            json={
                "name": "Original Corp",
                "slug": "original-corp",
                "contact_email": "admin@orig.example.com",
            },
        )
        assert response1.status_code == 201

        # Second request with same key but different body
        response2 = client.post(
            "/api/tenants",
            headers={"Idempotency-Key": idempotency_key},
            json={
                "name": "Different Corp",
                "slug": "different-corp",
                "contact_email": "admin@diff.example.com",
            },
        )
        assert response2.status_code == 409
        assert response2.json()["error"] == "idempotency_mismatch"

    def test_different_idempotency_keys_create_separate_tenants(
        self,
        client: TestClient,
        platform_admin_principal: MockPrincipal,
    ):
        """Test that different idempotency keys create separate tenants."""
        inject_principal(client, platform_admin_principal)

        response1 = client.post(
            "/api/tenants",
            headers={"Idempotency-Key": f"idem-{uuid4()}"},
            json={
                "name": "Tenant A",
                "slug": "tenant-a",
                "contact_email": "admin@a.example.com",
            },
        )
        assert response1.status_code == 201

        response2 = client.post(
            "/api/tenants",
            headers={"Idempotency-Key": f"idem-{uuid4()}"},
            json={
                "name": "Tenant B",
                "slug": "tenant-b",
                "contact_email": "admin@b.example.com",
            },
        )
        assert response2.status_code == 201

        assert (
            response1.json()["tenant"]["tenant_id"]
            != response2.json()["tenant"]["tenant_id"]
        )


class TestRBACEnforcement:
    """Tests for RBAC authorization checks."""

    def test_unauthenticated_request_returns_401(self, client: TestClient):
        """Test that requests without authentication return 401."""
        inject_principal(client, None)

        response = client.post(
            "/api/tenants",
            json={
                "name": "Unauthorized Corp",
                "slug": "unauth-corp",
                "contact_email": "admin@unauth.example.com",
            },
        )

        assert response.status_code == 401
        assert response.json()["error"] == "unauthenticated"

    def test_tenant_admin_returns_403(
        self,
        client: TestClient,
        tenant_admin_principal: MockPrincipal,
    ):
        """Test that tenant_admin role cannot create tenants (needs platform_admin)."""
        inject_principal(client, tenant_admin_principal)

        response = client.post(
            "/api/tenants",
            json={
                "name": "Forbidden Corp",
                "slug": "forbidden-corp",
                "contact_email": "admin@forbidden.example.com",
            },
        )

        assert response.status_code == 403
        assert response.json()["error"] == "forbidden"
        assert "PlatformAdmin" in response.json()["message"]

    def test_learner_returns_403(
        self,
        client: TestClient,
        learner_principal: MockPrincipal,
    ):
        """Test that learner role cannot create tenants."""
        inject_principal(client, learner_principal)

        response = client.post(
            "/api/tenants",
            json={
                "name": "Learner Corp",
                "slug": "learner-corp",
                "contact_email": "admin@learner.example.com",
            },
        )

        assert response.status_code == 403

    def test_platform_admin_can_create(
        self,
        client: TestClient,
        platform_admin_principal: MockPrincipal,
    ):
        """Test that platform_admin role can create tenants."""
        inject_principal(client, platform_admin_principal)

        response = client.post(
            "/api/tenants",
            json={
                "name": "Admin Corp",
                "slug": "admin-corp",
                "contact_email": "admin@admin.example.com",
            },
        )

        assert response.status_code == 201

    def test_tenants_admin_permission_can_create(
        self,
        client: TestClient,
    ):
        """Test that tenants:admin permission allows tenant creation."""
        principal = MockPrincipal(
            subject=str(uuid4()),
            tenant_id=str(uuid4()),
            roles=("service_account",),
            scopes=(),
            effective_permissions=frozenset(["tenants:admin"]),
        )
        inject_principal(client, principal)

        response = client.post(
            "/api/tenants",
            json={
                "name": "Service Corp",
                "slug": "service-corp",
                "contact_email": "admin@service.example.com",
            },
        )

        assert response.status_code == 201


class TestTenantIsolation:
    """Tests for tenant data isolation."""

    def test_tenant_has_unique_id(
        self,
        client: TestClient,
        platform_admin_principal: MockPrincipal,
    ):
        """Test that each tenant gets a unique UUID."""
        inject_principal(client, platform_admin_principal)

        tenant_ids = []
        for i in range(3):
            response = client.post(
                "/api/tenants",
                json={
                    "name": f"Unique Corp {i}",
                    "slug": f"unique-corp-{i}",
                    "contact_email": f"admin{i}@unique.example.com",
                },
            )
            assert response.status_code == 201
            tenant_ids.append(response.json()["tenant"]["tenant_id"])

        # All IDs should be unique
        assert len(tenant_ids) == len(set(tenant_ids))

    def test_tenant_data_contains_partition_key(
        self,
        client: TestClient,
        platform_admin_principal: MockPrincipal,
    ):
        """Test that tenant response includes tenant_id as partition key."""
        inject_principal(client, platform_admin_principal)

        response = client.post(
            "/api/tenants",
            json={
                "name": "Partition Corp",
                "slug": "partition-corp",
                "contact_email": "admin@partition.example.com",
            },
        )

        assert response.status_code == 201
        tenant = response.json()["tenant"]
        assert "tenant_id" in tenant
        # Validate UUID format
        from uuid import UUID

        UUID(tenant["tenant_id"])  # Raises if invalid


class TestEventEmission:
    """Tests for provisioning event emission."""

    def test_successful_provisioning_emits_events(
        self,
        client: TestClient,
        platform_admin_principal: MockPrincipal,
        event_publisher: TestEventPublisher,
    ):
        """Test that successful provisioning emits start and complete events."""
        inject_principal(client, platform_admin_principal)

        response = client.post(
            "/api/tenants",
            json={
                "name": "Event Corp",
                "slug": "event-corp",
                "contact_email": "admin@event.example.com",
            },
        )

        assert response.status_code == 201
        tenant_id = response.json()["tenant"]["tenant_id"]

        # Check events
        assert len(event_publisher.events) >= 2

        started_event = next(
            (e for e in event_publisher.events if e["type"] == "tenant.provisioning.started"),
            None,
        )
        assert started_event is not None
        assert started_event["data"]["tenant_id"] == tenant_id

        completed_event = next(
            (e for e in event_publisher.events if e["type"] == "tenant.provisioning.completed"),
            None,
        )
        assert completed_event is not None
        assert completed_event["data"]["tenant_id"] == tenant_id
        assert completed_event["data"]["name"] == "Event Corp"
        assert completed_event["data"]["slug"] == "event-corp"

    def test_event_is_tenant_scoped(
        self,
        client: TestClient,
        platform_admin_principal: MockPrincipal,
        event_publisher: TestEventPublisher,
    ):
        """Test that events contain tenant_id for scoping."""
        inject_principal(client, platform_admin_principal)

        response = client.post(
            "/api/tenants",
            json={
                "name": "Scoped Corp",
                "slug": "scoped-corp",
                "contact_email": "admin@scoped.example.com",
            },
        )

        assert response.status_code == 201
        tenant_id = response.json()["tenant"]["tenant_id"]

        for event in event_publisher.events:
            # All events should have tenant_id in data
            assert event["data"]["tenant_id"] == tenant_id
            # Subject should contain tenant path
            assert f"tenant/{tenant_id}" in event["subject"]

    def test_event_includes_correlation_id(
        self,
        client: TestClient,
        platform_admin_principal: MockPrincipal,
        event_publisher: TestEventPublisher,
    ):
        """Test that events include correlation ID for tracing."""
        inject_principal(client, platform_admin_principal)
        correlation_id = f"corr-{uuid4()}"

        response = client.post(
            "/api/tenants",
            headers={"X-Correlation-ID": correlation_id},
            json={
                "name": "Correlated Corp",
                "slug": "correlated-corp",
                "contact_email": "admin@corr.example.com",
            },
        )

        assert response.status_code == 201

        for event in event_publisher.events:
            assert event["data"]["correlation_id"] == correlation_id


class TestValidation:
    """Tests for request validation."""

    def test_invalid_slug_rejected(
        self,
        client: TestClient,
        platform_admin_principal: MockPrincipal,
    ):
        """Test that invalid slug format is rejected."""
        inject_principal(client, platform_admin_principal)

        # Slug with uppercase
        response = client.post(
            "/api/tenants",
            json={
                "name": "Invalid Slug Corp",
                "slug": "Invalid-Slug",
                "contact_email": "admin@invalid.example.com",
            },
        )
        assert response.status_code == 422

        # Slug starting with hyphen
        response = client.post(
            "/api/tenants",
            json={
                "name": "Invalid Slug Corp",
                "slug": "-invalid-slug",
                "contact_email": "admin@invalid.example.com",
            },
        )
        assert response.status_code == 422

    def test_invalid_email_rejected(
        self,
        client: TestClient,
        platform_admin_principal: MockPrincipal,
    ):
        """Test that invalid email format is rejected."""
        inject_principal(client, platform_admin_principal)

        response = client.post(
            "/api/tenants",
            json={
                "name": "Invalid Email Corp",
                "slug": "invalid-email",
                "contact_email": "not-an-email",
            },
        )
        assert response.status_code == 422

    def test_missing_required_fields_rejected(
        self,
        client: TestClient,
        platform_admin_principal: MockPrincipal,
    ):
        """Test that missing required fields are rejected."""
        inject_principal(client, platform_admin_principal)

        # Missing name
        response = client.post(
            "/api/tenants",
            json={
                "slug": "no-name",
                "contact_email": "admin@noname.example.com",
            },
        )
        assert response.status_code == 422

        # Missing slug
        response = client.post(
            "/api/tenants",
            json={
                "name": "No Slug Corp",
                "contact_email": "admin@noslug.example.com",
            },
        )
        assert response.status_code == 422

        # Missing email
        response = client.post(
            "/api/tenants",
            json={
                "name": "No Email Corp",
                "slug": "no-email",
            },
        )
        assert response.status_code == 422


class TestHealthCheck:
    """Tests for health check endpoint."""

    def test_health_check_returns_healthy(self, client: TestClient):
        """Test that health check returns healthy status."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "tenant-provisioning"
