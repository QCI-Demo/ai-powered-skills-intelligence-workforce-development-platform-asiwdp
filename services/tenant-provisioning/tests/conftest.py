"""Pytest configuration and fixtures for tenant provisioning tests."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.controllers.tenant_controller import (
    InMemoryIdempotencyStore,
    InMemoryTenantRepository,
    set_idempotency_store,
    set_tenant_repository,
)
from src.events.publisher import (
    EventPublisher,
    set_event_publisher,
)
from src.main import create_app


class MockPrincipal:
    """Mock principal for testing authentication/authorization."""

    def __init__(
        self,
        subject: str,
        tenant_id: str | None = None,
        roles: tuple[str, ...] = (),
        scopes: tuple[str, ...] = (),
        effective_permissions: frozenset[str] = frozenset(),
    ):
        self.subject = subject
        self.tenant_id = tenant_id
        self.roles = roles
        self.scopes = scopes
        self.effective_permissions = effective_permissions


class TestEventPublisher(EventPublisher):
    """Event publisher that captures events for testing."""

    def __init__(self):
        super().__init__(event_bus_url=None)
        self.events: list[dict[str, Any]] = []

    async def publish(self, event) -> bool:
        self.events.append(event.to_event_bus_format())
        return True


@pytest.fixture
def tenant_repository() -> InMemoryTenantRepository:
    """Fresh in-memory tenant repository for each test."""
    repo = InMemoryTenantRepository()
    set_tenant_repository(repo)
    return repo


@pytest.fixture
def idempotency_store() -> InMemoryIdempotencyStore:
    """Fresh in-memory idempotency store for each test."""
    store = InMemoryIdempotencyStore()
    set_idempotency_store(store)
    return store


@pytest.fixture
def event_publisher() -> TestEventPublisher:
    """Event publisher that captures events."""
    publisher = TestEventPublisher()
    set_event_publisher(publisher)
    return publisher


@pytest.fixture
def app(
    tenant_repository: InMemoryTenantRepository,
    idempotency_store: InMemoryIdempotencyStore,
    event_publisher: TestEventPublisher,
):
    """FastAPI test app with mocked dependencies."""
    return create_app()


@pytest.fixture
def client(app) -> Generator[TestClient, None, None]:
    """Test client with mocked authentication."""
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def platform_admin_principal() -> MockPrincipal:
    """Principal with platform_admin role."""
    return MockPrincipal(
        subject=str(uuid4()),
        tenant_id=None,  # Platform admin may not have tenant
        roles=("platform_admin",),
        scopes=(),
        effective_permissions=frozenset(["*"]),
    )


@pytest.fixture
def tenant_admin_principal() -> MockPrincipal:
    """Principal with tenant_admin role (insufficient for provisioning)."""
    return MockPrincipal(
        subject=str(uuid4()),
        tenant_id=str(uuid4()),
        roles=("tenant_admin",),
        scopes=(),
        effective_permissions=frozenset([
            "tenants:read",
            "tenants:write",
            "users:admin",
        ]),
    )


@pytest.fixture
def learner_principal() -> MockPrincipal:
    """Principal with learner role (minimal permissions)."""
    return MockPrincipal(
        subject=str(uuid4()),
        tenant_id=str(uuid4()),
        roles=("learner",),
        scopes=(),
        effective_permissions=frozenset([
            "skills:read",
            "progress:read",
            "progress:write",
        ]),
    )


def inject_principal(client: TestClient, principal: MockPrincipal | None):
    """Inject a mock principal into the request state."""
    original_call = client.app.__call__

    async def patched_call(scope, receive, send):
        if scope["type"] == "http":
            state = scope.setdefault("state", {})
            state["principal"] = principal
        return await original_call(scope, receive, send)

    client.app.__call__ = patched_call
