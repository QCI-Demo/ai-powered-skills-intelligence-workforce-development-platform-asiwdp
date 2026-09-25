"""Test fixtures and configuration.

Task: 0abf33e9-7e7b-4c21-8bae-3b36041ab006
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from tenant_provisioning.database import Base, TenantRepository
from tenant_provisioning.events import InMemoryEventPublisher


@dataclass(frozen=True, slots=True)
class MockPrincipal:
    """Mock principal for testing RBAC."""

    subject: str
    tenant_id: str | None
    roles: tuple[str, ...]
    scopes: tuple[str, ...]
    effective_permissions: frozenset[str]
    actor_type: str = "user"
    session_id: str | None = None
    org_id: str | None = None

    def has_permission(self, permission: str) -> bool:
        if "*" in self.effective_permissions:
            return True
        return permission in self.effective_permissions

    def has_role(self, role: str) -> bool:
        return role in self.roles


def create_mock_principal(
    subject: str = "test-user",
    tenant_id: str | None = None,
    roles: tuple[str, ...] = (),
    permissions: frozenset[str] = frozenset(),
) -> MockPrincipal:
    """Create a mock principal for testing."""
    return MockPrincipal(
        subject=subject,
        tenant_id=tenant_id,
        roles=roles,
        scopes=(),
        effective_permissions=permissions,
    )


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def async_engine():
    """Create async SQLite engine for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Enable foreign keys for SQLite
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(async_engine) -> async_sessionmaker[AsyncSession]:
    """Create session factory for tests."""
    return async_sessionmaker(async_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def repository(session_factory) -> TenantRepository:
    """Create repository for tests."""
    return TenantRepository(session_factory)


@pytest.fixture
def event_publisher() -> InMemoryEventPublisher:
    """Create in-memory event publisher for tests."""
    return InMemoryEventPublisher()


@pytest.fixture
def platform_admin_principal() -> MockPrincipal:
    """Create platform admin principal."""
    return create_mock_principal(
        subject="platform-admin-user",
        tenant_id=None,
        roles=("platform_admin",),
        permissions=frozenset(["*"]),
    )


@pytest.fixture
def tenant_admin_principal() -> MockPrincipal:
    """Create tenant admin principal (should NOT be able to create tenants)."""
    return create_mock_principal(
        subject="tenant-admin-user",
        tenant_id="existing-tenant-id",
        roles=("tenant_admin",),
        permissions=frozenset([
            "tenants:read",
            "tenants:write",
            "users:admin",
        ]),
    )


@pytest.fixture
def learner_principal() -> MockPrincipal:
    """Create learner principal (should NOT be able to create tenants)."""
    return create_mock_principal(
        subject="learner-user",
        tenant_id="existing-tenant-id",
        roles=("learner",),
        permissions=frozenset([
            "skills:read",
            "progress:read",
            "progress:write",
        ]),
    )


@pytest.fixture
def valid_tenant_request() -> dict[str, Any]:
    """Create valid tenant creation request."""
    return {
        "name": "Test Tenant",
        "slug": "test-tenant",
        "metadata": {
            "industry": "Technology",
            "region": "us-west-2",
        },
    }
