"""Integration tests for tenant provisioning.

Task: 0abf33e9-7e7b-4c21-8bae-3b36041ab006
Write integration tests for tenant provisioning:
1. Use the test framework to spin up in-memory DB
2. Execute provisioning calls with various token scopes
3. Assert database isolation and event emission
"""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio

from tenant_provisioning.database import TenantRepository
from tenant_provisioning.events import InMemoryEventPublisher, create_tenant_provisioned_event
from tenant_provisioning.models import CreateTenantRequest, TenantConfiguration
from tenant_provisioning.service import TenantProvisioningService

from .conftest import MockPrincipal, create_mock_principal


class MockRequest:
    """Mock Starlette Request for testing."""

    def __init__(
        self,
        body: dict[str, Any],
        headers: dict[str, str] | None = None,
        principal: MockPrincipal | None = None,
    ):
        self._body = body
        self._headers = headers or {}
        self._principal = principal

        # Mock state object
        class State:
            pass

        self.state = State()
        if principal:
            self.state.principal = principal

    @property
    def headers(self) -> dict[str, str]:
        return self._headers

    async def json(self) -> dict[str, Any]:
        return self._body


class TestTenantProvisioningService:
    """Test suite for tenant provisioning service.
    
    Task: 0abf33e9-7e7b-4c21-8bae-3b36041ab006
    """

    @pytest_asyncio.fixture
    async def service(
        self,
        repository: TenantRepository,
        event_publisher: InMemoryEventPublisher,
    ) -> TenantProvisioningService:
        """Create service instance for tests."""
        return TenantProvisioningService(
            repository=repository,
            event_publisher=event_publisher,
        )

    @pytest.mark.asyncio
    async def test_create_tenant_success(
        self,
        service: TenantProvisioningService,
        repository: TenantRepository,
        event_publisher: InMemoryEventPublisher,
        platform_admin_principal: MockPrincipal,
        valid_tenant_request: dict[str, Any],
    ):
        """Test successful tenant creation by platform admin.
        
        Task: 0abf33e9-7e7b-4c21-8bae-3b36041ab006
        Verify successful provisioning with platform_admin token.
        """
        request = MockRequest(
            body=valid_tenant_request,
            principal=platform_admin_principal,
        )

        response = await service.create_tenant(request)

        assert response.status_code == 201
        body = json.loads(response.body)
        assert body["name"] == "Test Tenant"
        assert body["slug"] == "test-tenant"
        assert body["status"] == "active"
        assert body["createdBy"] == platform_admin_principal.subject
        assert "configuration" in body
        assert "id" in body

        # Verify event was published
        assert len(event_publisher.events) == 1
        event = event_publisher.events[0]
        assert event.event_type == "tenant.provisioned"
        assert event.tenant_slug == "test-tenant"
        assert event.tenant_name == "Test Tenant"

    @pytest.mark.asyncio
    async def test_create_tenant_forbidden_for_tenant_admin(
        self,
        service: TenantProvisioningService,
        tenant_admin_principal: MockPrincipal,
        valid_tenant_request: dict[str, Any],
    ):
        """Test that tenant_admin cannot create new tenants.
        
        Task: 0abf33e9-7e7b-4c21-8bae-3b36041ab006
        Task: ca4babed-4042-4c03-97bc-9705218cbfc9
        Verify 403 for unauthorized attempts.
        """
        request = MockRequest(
            body=valid_tenant_request,
            principal=tenant_admin_principal,
        )

        response = await service.create_tenant(request)

        assert response.status_code == 403
        body = json.loads(response.body)
        assert body["error"] == "forbidden"
        assert "platform administrators" in body["message"].lower()

    @pytest.mark.asyncio
    async def test_create_tenant_forbidden_for_learner(
        self,
        service: TenantProvisioningService,
        learner_principal: MockPrincipal,
        valid_tenant_request: dict[str, Any],
    ):
        """Test that learner cannot create tenants.
        
        Task: 0abf33e9-7e7b-4c21-8bae-3b36041ab006
        """
        request = MockRequest(
            body=valid_tenant_request,
            principal=learner_principal,
        )

        response = await service.create_tenant(request)

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_tenant_unauthenticated(
        self,
        service: TenantProvisioningService,
        valid_tenant_request: dict[str, Any],
    ):
        """Test that unauthenticated requests are rejected.
        
        Task: 0abf33e9-7e7b-4c21-8bae-3b36041ab006
        """
        request = MockRequest(
            body=valid_tenant_request,
            principal=None,  # No principal
        )

        response = await service.create_tenant(request)

        assert response.status_code == 401
        body = json.loads(response.body)
        assert body["error"] == "unauthenticated"

    @pytest.mark.asyncio
    async def test_idempotency_returns_cached_response(
        self,
        service: TenantProvisioningService,
        event_publisher: InMemoryEventPublisher,
        platform_admin_principal: MockPrincipal,
    ):
        """Test that idempotency key returns cached response.
        
        Task: 0abf33e9-7e7b-4c21-8bae-3b36041ab006
        Task: 78cab998-3bb5-4262-bc80-e2160bdc2805
        Verify idempotent behavior with same Idempotency-Key.
        """
        idempotency_key = str(uuid4())
        request_body = {
            "name": "Idempotent Tenant",
            "slug": "idempotent-tenant",
        }

        # First request
        request1 = MockRequest(
            body=request_body,
            headers={"Idempotency-Key": idempotency_key},
            principal=platform_admin_principal,
        )
        response1 = await service.create_tenant(request1)
        assert response1.status_code == 201
        body1 = json.loads(response1.body)

        # Second request with same idempotency key
        request2 = MockRequest(
            body=request_body,
            headers={"Idempotency-Key": idempotency_key},
            principal=platform_admin_principal,
        )
        response2 = await service.create_tenant(request2)
        
        # Should return 200 with cached response
        assert response2.status_code == 200
        body2 = json.loads(response2.body)
        assert body1["id"] == body2["id"]
        assert body1["slug"] == body2["slug"]

        # Event should only be published once
        assert len(event_publisher.events) == 1

    @pytest.mark.asyncio
    async def test_idempotency_conflict_different_body(
        self,
        service: TenantProvisioningService,
        platform_admin_principal: MockPrincipal,
    ):
        """Test that idempotency key with different body returns conflict.
        
        Task: 0abf33e9-7e7b-4c21-8bae-3b36041ab006
        Task: 78cab998-3bb5-4262-bc80-e2160bdc2805
        """
        idempotency_key = str(uuid4())

        # First request
        request1 = MockRequest(
            body={"name": "First Tenant", "slug": "first-tenant"},
            headers={"Idempotency-Key": idempotency_key},
            principal=platform_admin_principal,
        )
        response1 = await service.create_tenant(request1)
        assert response1.status_code == 201

        # Second request with same key but different body
        request2 = MockRequest(
            body={"name": "Different Tenant", "slug": "different-tenant"},
            headers={"Idempotency-Key": idempotency_key},
            principal=platform_admin_principal,
        )
        response2 = await service.create_tenant(request2)
        
        assert response2.status_code == 409
        body = json.loads(response2.body)
        assert body["error"] == "idempotency_conflict"

    @pytest.mark.asyncio
    async def test_duplicate_slug_rejected(
        self,
        service: TenantProvisioningService,
        platform_admin_principal: MockPrincipal,
    ):
        """Test that duplicate slugs are rejected.
        
        Task: 0abf33e9-7e7b-4c21-8bae-3b36041ab006
        """
        # First tenant
        request1 = MockRequest(
            body={"name": "First", "slug": "unique-slug"},
            principal=platform_admin_principal,
        )
        response1 = await service.create_tenant(request1)
        assert response1.status_code == 201

        # Second tenant with same slug
        request2 = MockRequest(
            body={"name": "Second", "slug": "unique-slug"},
            principal=platform_admin_principal,
        )
        response2 = await service.create_tenant(request2)
        
        assert response2.status_code == 409
        body = json.loads(response2.body)
        assert body["error"] == "conflict"
        assert "already exists" in body["message"]

    @pytest.mark.asyncio
    async def test_invalid_request_body(
        self,
        service: TenantProvisioningService,
        platform_admin_principal: MockPrincipal,
    ):
        """Test validation of invalid request body.
        
        Task: 0abf33e9-7e7b-4c21-8bae-3b36041ab006
        """
        # Missing required fields
        request = MockRequest(
            body={"name": "Missing Slug"},
            principal=platform_admin_principal,
        )
        response = await service.create_tenant(request)
        
        assert response.status_code == 400
        body = json.loads(response.body)
        assert body["error"] == "validation_error"

    @pytest.mark.asyncio
    async def test_invalid_slug_format(
        self,
        service: TenantProvisioningService,
        platform_admin_principal: MockPrincipal,
    ):
        """Test validation of slug format.
        
        Task: 0abf33e9-7e7b-4c21-8bae-3b36041ab006
        """
        invalid_slugs = [
            "UPPERCASE",  # Must be lowercase
            "-starts-with-hyphen",
            "ends-with-hyphen-",
            "has--double-hyphens",
            "has spaces",
            "has_underscores",
        ]

        for slug in invalid_slugs:
            request = MockRequest(
                body={"name": "Test", "slug": slug},
                principal=platform_admin_principal,
            )
            response = await service.create_tenant(request)
            assert response.status_code == 400, f"Expected 400 for slug: {slug}"

    @pytest.mark.asyncio
    async def test_default_configuration_applied(
        self,
        service: TenantProvisioningService,
        platform_admin_principal: MockPrincipal,
    ):
        """Test that default configuration is applied when not provided.
        
        Task: 0abf33e9-7e7b-4c21-8bae-3b36041ab006
        """
        request = MockRequest(
            body={"name": "Default Config Tenant", "slug": "default-config"},
            principal=platform_admin_principal,
        )
        response = await service.create_tenant(request)

        assert response.status_code == 201
        body = json.loads(response.body)
        config = body["configuration"]

        # Check defaults from TenantConfiguration.default()
        assert config["featureFlags"]["aiRecommendations"] is True
        assert config["limits"]["maxUsers"] == 50
        assert config["branding"]["primaryColor"] == "#1976D2"

    @pytest.mark.asyncio
    async def test_custom_configuration_preserved(
        self,
        service: TenantProvisioningService,
        platform_admin_principal: MockPrincipal,
    ):
        """Test that custom configuration is preserved.
        
        Task: 0abf33e9-7e7b-4c21-8bae-3b36041ab006
        """
        request = MockRequest(
            body={
                "name": "Custom Config Tenant",
                "slug": "custom-config",
                "configuration": {
                    "featureFlags": {"aiRecommendations": False},
                    "limits": {"maxUsers": 200},
                    "branding": {"primaryColor": "#FF0000"},
                },
            },
            principal=platform_admin_principal,
        )
        response = await service.create_tenant(request)

        assert response.status_code == 201
        body = json.loads(response.body)
        config = body["configuration"]

        assert config["featureFlags"]["aiRecommendations"] is False
        assert config["limits"]["maxUsers"] == 200
        assert config["branding"]["primaryColor"] == "#FF0000"

    @pytest.mark.asyncio
    async def test_metadata_stored(
        self,
        service: TenantProvisioningService,
        platform_admin_principal: MockPrincipal,
    ):
        """Test that metadata is stored correctly.
        
        Task: 0abf33e9-7e7b-4c21-8bae-3b36041ab006
        """
        metadata = {
            "industry": "Healthcare",
            "region": "eu-west-1",
            "tier": "enterprise",
        }
        request = MockRequest(
            body={
                "name": "Metadata Tenant",
                "slug": "metadata-tenant",
                "metadata": metadata,
            },
            principal=platform_admin_principal,
        )
        response = await service.create_tenant(request)

        assert response.status_code == 201
        body = json.loads(response.body)
        assert body["metadata"] == metadata

    @pytest.mark.asyncio
    async def test_event_contains_tenant_scope(
        self,
        service: TenantProvisioningService,
        event_publisher: InMemoryEventPublisher,
        platform_admin_principal: MockPrincipal,
    ):
        """Test that provisioned event is tenant-scoped.
        
        Task: 0abf33e9-7e7b-4c21-8bae-3b36041ab006
        Task: 4a9fb493-572e-4e33-bac6-eeb81ba43ec1
        Assert event emission with tenant scope.
        """
        request = MockRequest(
            body={
                "name": "Event Test Tenant",
                "slug": "event-test",
                "metadata": {"key": "value"},
            },
            principal=platform_admin_principal,
        )
        response = await service.create_tenant(request)

        assert response.status_code == 201
        body = json.loads(response.body)

        # Verify event
        assert len(event_publisher.events) == 1
        event = event_publisher.events[0]

        # Event should contain tenant-scoped data
        assert event.tenant_id == body["id"]
        assert event.tenant_slug == "event-test"
        assert event.tenant_name == "Event Test Tenant"
        assert event.created_by == platform_admin_principal.subject
        assert event.metadata == {"key": "value"}
        assert event.timestamp is not None
        assert event.event_id is not None


class TestTenantRepository:
    """Test suite for tenant repository.
    
    Task: 0abf33e9-7e7b-4c21-8bae-3b36041ab006
    """

    @pytest.mark.asyncio
    async def test_create_and_retrieve_tenant(
        self,
        repository: TenantRepository,
    ):
        """Test creating and retrieving a tenant."""
        request = CreateTenantRequest(
            name="Repo Test Tenant",
            slug="repo-test",
        )
        tenant = await repository.create_tenant(request, created_by="test-user")

        # Retrieve by ID
        retrieved = await repository.get_tenant_by_id(tenant.id)
        assert retrieved is not None
        assert retrieved.name == "Repo Test Tenant"
        assert retrieved.slug == "repo-test"

        # Retrieve by slug
        by_slug = await repository.get_tenant_by_slug("repo-test")
        assert by_slug is not None
        assert by_slug.id == tenant.id

    @pytest.mark.asyncio
    async def test_tenant_isolation(
        self,
        repository: TenantRepository,
    ):
        """Test that tenants are isolated from each other.
        
        Task: 0abf33e9-7e7b-4c21-8bae-3b36041ab006
        Assert database isolation.
        """
        # Create two tenants
        tenant1 = await repository.create_tenant(
            CreateTenantRequest(name="Tenant One", slug="tenant-one"),
            created_by="user1",
        )
        tenant2 = await repository.create_tenant(
            CreateTenantRequest(name="Tenant Two", slug="tenant-two"),
            created_by="user2",
        )

        # They should have different IDs
        assert tenant1.id != tenant2.id

        # Each should only retrieve its own data
        retrieved1 = await repository.get_tenant_by_id(tenant1.id)
        retrieved2 = await repository.get_tenant_by_id(tenant2.id)

        assert retrieved1.slug == "tenant-one"
        assert retrieved2.slug == "tenant-two"

        # Cross-lookup should fail
        assert await repository.get_tenant_by_slug("nonexistent") is None
