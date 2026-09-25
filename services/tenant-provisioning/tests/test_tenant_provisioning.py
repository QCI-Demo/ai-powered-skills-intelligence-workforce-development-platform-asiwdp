"""Integration tests for tenant provisioning service."""

from __future__ import annotations

from uuid import uuid4

import pytest

from tests.conftest import MockPrincipal, create_tenant_payload


class TestTenantProvisioning:
    """Tests for POST /api/tenants endpoint."""

    @pytest.mark.asyncio
    async def test_create_tenant_success(self, auth_client):
        """Test successful tenant creation by platform admin."""
        client, principals = auth_client
        payload = create_tenant_payload(name="acme-corp")

        response = await client.post(
            "/api/tenants",
            json=payload,
            headers={"X-Test-Role": "platform_admin"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["tenant"]["name"] == "acme-corp"
        assert data["tenant"]["status"] == "active"
        assert data["tenant"]["plan_tier"] == "starter"
        assert len(data["configurations"]) > 0
        assert data["idempotent"] is False

    @pytest.mark.asyncio
    async def test_create_tenant_with_all_fields(self, auth_client):
        """Test tenant creation with all optional fields."""
        client, _ = auth_client
        payload = create_tenant_payload(
            name="full-tenant",
            display_name="Full Tenant Corp",
            domain="full-tenant.example.com",
            plan_tier="enterprise",
            settings={"custom_theme": "dark"},
            metadata={"industry": "technology", "region": "us-west"},
        )

        response = await client.post(
            "/api/tenants",
            json=payload,
            headers={"X-Test-Role": "platform_admin"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["tenant"]["display_name"] == "Full Tenant Corp"
        assert data["tenant"]["domain"] == "full-tenant.example.com"
        assert data["tenant"]["plan_tier"] == "enterprise"
        assert data["tenant"]["settings"]["custom_theme"] == "dark"

    @pytest.mark.asyncio
    async def test_create_tenant_invalid_name(self, auth_client):
        """Test validation rejects invalid tenant names."""
        client, _ = auth_client
        payload = create_tenant_payload(name="Invalid Name With Spaces!")

        response = await client.post(
            "/api/tenants",
            json=payload,
            headers={"X-Test-Role": "platform_admin"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_tenant_duplicate_name(self, auth_client):
        """Test duplicate tenant name returns 409."""
        client, _ = auth_client
        payload = create_tenant_payload(name="duplicate-test")

        # First creation should succeed
        response1 = await client.post(
            "/api/tenants",
            json=payload,
            headers={"X-Test-Role": "platform_admin"},
        )
        assert response1.status_code == 201

        # Second creation should fail
        response2 = await client.post(
            "/api/tenants",
            json=payload,
            headers={"X-Test-Role": "platform_admin"},
        )
        assert response2.status_code == 409
        assert response2.json()["error"] == "conflict"


class TestIdempotency:
    """Tests for idempotency key handling."""

    @pytest.mark.asyncio
    async def test_idempotency_same_request(self, auth_client):
        """Test same idempotency key returns cached response."""
        client, _ = auth_client
        payload = create_tenant_payload(name="idempotent-tenant")
        idempotency_key = str(uuid4())

        # First request
        response1 = await client.post(
            "/api/tenants",
            json=payload,
            headers={
                "X-Test-Role": "platform_admin",
                "Idempotency-Key": idempotency_key,
            },
        )
        assert response1.status_code == 201
        assert "X-Idempotent-Replay" not in response1.headers

        # Second request with same key and payload
        response2 = await client.post(
            "/api/tenants",
            json=payload,
            headers={
                "X-Test-Role": "platform_admin",
                "Idempotency-Key": idempotency_key,
            },
        )
        assert response2.status_code == 201
        assert response2.headers.get("X-Idempotent-Replay") == "true"

        # Response should be identical
        assert response1.json()["tenant"]["tenant_id"] == response2.json()["tenant"]["tenant_id"]

    @pytest.mark.asyncio
    async def test_idempotency_different_payload(self, auth_client):
        """Test same idempotency key with different payload returns 409."""
        client, _ = auth_client
        idempotency_key = str(uuid4())

        # First request
        payload1 = create_tenant_payload(name="idem-tenant-a")
        response1 = await client.post(
            "/api/tenants",
            json=payload1,
            headers={
                "X-Test-Role": "platform_admin",
                "Idempotency-Key": idempotency_key,
            },
        )
        assert response1.status_code == 201

        # Second request with different payload
        payload2 = create_tenant_payload(name="idem-tenant-b")
        response2 = await client.post(
            "/api/tenants",
            json=payload2,
            headers={
                "X-Test-Role": "platform_admin",
                "Idempotency-Key": idempotency_key,
            },
        )
        assert response2.status_code == 409
        assert response2.json()["error"] == "idempotency_conflict"

    @pytest.mark.asyncio
    async def test_without_idempotency_key(self, auth_client):
        """Test requests without idempotency key work normally."""
        client, _ = auth_client
        payload = create_tenant_payload()

        response = await client.post(
            "/api/tenants",
            json=payload,
            headers={"X-Test-Role": "platform_admin"},
        )
        assert response.status_code == 201


class TestRBACEnforcement:
    """Tests for RBAC enforcement on provisioning endpoint."""

    @pytest.mark.asyncio
    async def test_platform_admin_can_create_tenant(self, auth_client):
        """Test platform admin can create tenants."""
        client, _ = auth_client
        payload = create_tenant_payload()

        response = await client.post(
            "/api/tenants",
            json=payload,
            headers={"X-Test-Role": "platform_admin"},
        )
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_tenant_admin_cannot_create_tenant(self, auth_client):
        """Test tenant admin cannot create new tenants."""
        client, _ = auth_client
        payload = create_tenant_payload()

        response = await client.post(
            "/api/tenants",
            json=payload,
            headers={"X-Test-Role": "tenant_admin"},
        )
        assert response.status_code == 403
        assert response.json()["error"] == "forbidden"

    @pytest.mark.asyncio
    async def test_regular_user_cannot_create_tenant(self, auth_client):
        """Test regular user cannot create tenants."""
        client, _ = auth_client
        payload = create_tenant_payload()

        response = await client.post(
            "/api/tenants",
            json=payload,
            headers={"X-Test-Role": "regular_user"},
        )
        assert response.status_code == 403
        assert response.json()["error"] == "forbidden"
        assert "PlatformAdmin" in response.json()["message"]

    @pytest.mark.asyncio
    async def test_tenant_admin_can_read_tenant(self, auth_client):
        """Test tenant admin can read tenant details."""
        client, principals = auth_client

        # Create tenant as platform admin
        payload = create_tenant_payload()
        create_response = await client.post(
            "/api/tenants",
            json=payload,
            headers={"X-Test-Role": "platform_admin"},
        )
        tenant_id = create_response.json()["tenant"]["tenant_id"]

        # Update tenant_admin principal to have matching permissions
        principals["tenant_admin"].effective_permissions = frozenset([
            "tenants:read", "tenants:write"
        ])

        # Read as tenant admin should succeed
        response = await client.get(
            f"/api/tenants/{tenant_id}",
            headers={"X-Test-Role": "tenant_admin"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_regular_user_cannot_read_tenant(self, auth_client):
        """Test regular user cannot read tenant details."""
        client, _ = auth_client

        # Create tenant as platform admin
        payload = create_tenant_payload()
        create_response = await client.post(
            "/api/tenants",
            json=payload,
            headers={"X-Test-Role": "platform_admin"},
        )
        tenant_id = create_response.json()["tenant"]["tenant_id"]

        # Read as regular user should fail
        response = await client.get(
            f"/api/tenants/{tenant_id}",
            headers={"X-Test-Role": "regular_user"},
        )
        assert response.status_code == 403


class TestTenantIsolation:
    """Tests for tenant data isolation."""

    @pytest.mark.asyncio
    async def test_tenants_have_separate_configurations(self, auth_client):
        """Test each tenant gets its own configuration set."""
        client, _ = auth_client

        # Create two tenants
        tenant1_payload = create_tenant_payload(name="tenant-one", plan_tier="starter")
        tenant2_payload = create_tenant_payload(name="tenant-two", plan_tier="enterprise")

        response1 = await client.post(
            "/api/tenants",
            json=tenant1_payload,
            headers={"X-Test-Role": "platform_admin"},
        )
        response2 = await client.post(
            "/api/tenants",
            json=tenant2_payload,
            headers={"X-Test-Role": "platform_admin"},
        )

        assert response1.status_code == 201
        assert response2.status_code == 201

        tenant1_configs = response1.json()["configurations"]
        tenant2_configs = response2.json()["configurations"]

        # Config IDs should be different
        tenant1_config_ids = {c["config_id"] for c in tenant1_configs}
        tenant2_config_ids = {c["config_id"] for c in tenant2_configs}
        assert tenant1_config_ids.isdisjoint(tenant2_config_ids)

        # Plan-specific configs should differ
        tenant1_max_users = next(
            c["config_value"] for c in tenant1_configs if c["config_key"] == "max_users"
        )
        tenant2_max_users = next(
            c["config_value"] for c in tenant2_configs if c["config_key"] == "max_users"
        )

        # Starter = 50, Enterprise = -1 (unlimited)
        assert tenant1_max_users == 50
        assert tenant2_max_users == -1

    @pytest.mark.asyncio
    async def test_tenant_configurations_endpoint(self, auth_client):
        """Test retrieving configurations for a specific tenant."""
        client, _ = auth_client

        # Create tenant
        payload = create_tenant_payload()
        create_response = await client.post(
            "/api/tenants",
            json=payload,
            headers={"X-Test-Role": "platform_admin"},
        )
        tenant_id = create_response.json()["tenant"]["tenant_id"]

        # Get configurations
        response = await client.get(
            f"/api/tenants/{tenant_id}/configurations",
            headers={"X-Test-Role": "platform_admin"},
        )
        assert response.status_code == 200
        configs = response.json()
        assert len(configs) > 0

        # Verify configuration categories
        categories = {c["category"] for c in configs}
        assert "general" in categories
        assert "security" in categories
        assert "feature_flags" in categories

    @pytest.mark.asyncio
    async def test_tenant_configurations_by_category(self, auth_client):
        """Test filtering configurations by category."""
        client, _ = auth_client

        # Create tenant
        payload = create_tenant_payload()
        create_response = await client.post(
            "/api/tenants",
            json=payload,
            headers={"X-Test-Role": "platform_admin"},
        )
        tenant_id = create_response.json()["tenant"]["tenant_id"]

        # Get only security configurations
        response = await client.get(
            f"/api/tenants/{tenant_id}/configurations?category=security",
            headers={"X-Test-Role": "platform_admin"},
        )
        assert response.status_code == 200
        configs = response.json()

        # All should be security category
        for config in configs:
            assert config["category"] == "security"


class TestEventEmission:
    """Tests for provisioning event emission."""

    @pytest.mark.asyncio
    async def test_provisioning_event_created(self, auth_client, db_engine):
        """Test that a provisioning event is created on tenant creation."""
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        from tenant_provisioning.entities import ProvisioningEvent

        client, _ = auth_client

        # Create tenant
        payload = create_tenant_payload(name="event-test-tenant")
        response = await client.post(
            "/api/tenants",
            json=payload,
            headers={"X-Test-Role": "platform_admin"},
        )
        assert response.status_code == 201
        tenant_id = response.json()["tenant"]["tenant_id"]

        # Query database for event
        session_factory = async_sessionmaker(db_engine, class_=AsyncSession)
        async with session_factory() as session:
            stmt = select(ProvisioningEvent).where(
                ProvisioningEvent.tenant_id == tenant_id
            )
            result = await session.execute(stmt)
            events = result.scalars().all()

        assert len(events) == 1
        event = events[0]
        assert event.event_type == "tenant.provisioned"
        assert event.event_payload["tenant_name"] == "event-test-tenant"
        assert event.event_payload["tenant_id"] == tenant_id

    @pytest.mark.asyncio
    async def test_event_contains_tenant_metadata(self, auth_client, db_engine):
        """Test that event payload includes tenant-scoped metadata."""
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        from tenant_provisioning.entities import ProvisioningEvent

        client, _ = auth_client

        # Create tenant with metadata
        payload = create_tenant_payload(
            name="metadata-event-tenant",
            domain="metadata.example.com",
            metadata={"industry": "healthcare"},
        )
        response = await client.post(
            "/api/tenants",
            json=payload,
            headers={"X-Test-Role": "platform_admin"},
        )
        tenant_id = response.json()["tenant"]["tenant_id"]

        # Query event
        session_factory = async_sessionmaker(db_engine, class_=AsyncSession)
        async with session_factory() as session:
            stmt = select(ProvisioningEvent).where(
                ProvisioningEvent.tenant_id == tenant_id
            )
            result = await session.execute(stmt)
            event = result.scalar_one()

        # Verify metadata in event
        assert event.event_payload["metadata"]["domain"] == "metadata.example.com"
        assert event.event_payload["metadata"]["industry"] == "healthcare"


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check(self, auth_client):
        """Test health endpoint returns healthy status."""
        client, _ = auth_client
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
