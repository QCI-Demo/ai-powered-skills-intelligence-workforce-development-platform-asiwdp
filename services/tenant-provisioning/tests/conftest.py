"""Test fixtures for tenant provisioning integration tests."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tenant_provisioning.entities import Base
from tenant_provisioning.main import create_app


# ---------------------------------------------------------------------------
# In-Memory Database Setup
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Create in-memory SQLite engine for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create database session for testing."""
    session_factory = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Mock Principal for Authentication
# ---------------------------------------------------------------------------


@dataclass
class MockPrincipal:
    """Mock principal for testing different roles."""

    subject: str
    tenant_id: str | None
    roles: tuple[str, ...]
    effective_permissions: frozenset[str]
    scopes: tuple[str, ...] = ()
    issuer: str = "https://auth.asiwdp.example"
    audience: tuple[str, ...] = ("asiwdp-api",)
    issued_at: int = 0
    expires_at: int = 0

    @classmethod
    def platform_admin(cls, subject: str = "admin-user") -> MockPrincipal:
        """Create a platform admin principal."""
        return cls(
            subject=subject,
            tenant_id=None,
            roles=("platform_admin",),
            effective_permissions=frozenset(["*"]),
        )

    @classmethod
    def tenant_admin(cls, tenant_id: str, subject: str = "tenant-admin") -> MockPrincipal:
        """Create a tenant admin principal."""
        return cls(
            subject=subject,
            tenant_id=tenant_id,
            roles=("tenant_admin",),
            effective_permissions=frozenset([
                "tenants:read", "tenants:write",
                "users:admin", "organizations:admin",
            ]),
        )

    @classmethod
    def regular_user(cls, tenant_id: str, subject: str = "user") -> MockPrincipal:
        """Create a regular user principal with limited permissions."""
        return cls(
            subject=subject,
            tenant_id=tenant_id,
            roles=("learner",),
            effective_permissions=frozenset([
                "skills:read", "learning_paths:read", "progress:read",
            ]),
        )


# ---------------------------------------------------------------------------
# Test Application Client
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def app_client(db_engine, db_session) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with mocked dependencies."""
    from tenant_provisioning import database

    # Override database session factory
    original_get_session_factory = database.get_session_factory

    def mock_session_factory():
        return async_sessionmaker(
            db_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    database.get_session_factory = mock_session_factory

    # Create app without auth middleware for testing
    app = create_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    # Restore original
    database.get_session_factory = original_get_session_factory


@pytest_asyncio.fixture(scope="function")
async def auth_client(db_engine) -> AsyncGenerator[tuple[AsyncClient, dict[str, MockPrincipal]], None]:
    """Create test client with authentication support."""
    from fastapi import FastAPI, Request
    from starlette.middleware.base import BaseHTTPMiddleware

    from tenant_provisioning import database
    from tenant_provisioning.router import router

    # Override database
    def mock_session_factory():
        return async_sessionmaker(
            db_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    database.get_session_factory = mock_session_factory

    # Create principals for different test scenarios
    principals = {
        "platform_admin": MockPrincipal.platform_admin(),
        "tenant_admin": MockPrincipal.tenant_admin(str(uuid4())),
        "regular_user": MockPrincipal.regular_user(str(uuid4())),
    }

    class MockAuthMiddleware(BaseHTTPMiddleware):
        """Middleware that injects mock principal based on header."""

        async def dispatch(self, request: Request, call_next):
            # Get role from test header
            role = request.headers.get("X-Test-Role", "platform_admin")
            principal = principals.get(role, principals["regular_user"])
            request.state.principal = principal
            return await call_next(request)

    app = FastAPI()
    app.add_middleware(MockAuthMiddleware)
    app.include_router(router)

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client, principals


# ---------------------------------------------------------------------------
# Test Data Factories
# ---------------------------------------------------------------------------


def create_tenant_payload(
    name: str | None = None,
    display_name: str | None = None,
    domain: str | None = None,
    plan_tier: str = "starter",
    settings: dict[str, Any] | None = None,
    metadata: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Create a valid tenant creation payload."""
    if name is None:
        name = f"test-tenant-{uuid4().hex[:8]}"
    return {
        "name": name,
        "display_name": display_name or f"Test Tenant {name}",
        "domain": domain,
        "plan_tier": plan_tier,
        "settings": settings or {},
        "metadata": metadata or {},
    }
