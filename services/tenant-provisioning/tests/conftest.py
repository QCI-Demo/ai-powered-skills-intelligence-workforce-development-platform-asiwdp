"""Test fixtures for tenant provisioning service."""

from __future__ import annotations

import time
from pathlib import Path
from typing import AsyncGenerator
from uuid import UUID

import jwt
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.applications import Starlette
from starlette.testclient import TestClient

from asiwdp_auth import AuthConfig, RbacPolicy
from tenant_provisioning.app import create_app
from tenant_provisioning.database import Base, DatabaseManager
from tenant_provisioning.events import InMemoryEventPublisher
from tenant_provisioning.service import TenantProvisioningService

# Test constants
REPO_ROOT = Path(__file__).resolve().parents[4]
RBAC_MATRIX = REPO_ROOT / "config" / "rbac" / "role-permission-matrix.yaml"

TEST_SECRET = "test-only-hs256-secret-not-for-production"
TEST_ISSUER = "https://auth.asiwdp.test/"
TEST_AUDIENCE = "asiwdp-api"

# Test user IDs
PLATFORM_ADMIN_ID = "00000000-0000-0000-0000-000000000001"
TENANT_ADMIN_ID = "00000000-0000-0000-0000-000000000002"
LEARNER_ID = "00000000-0000-0000-0000-000000000003"
TEST_TENANT_ID = "11111111-1111-1111-1111-111111111111"


def make_token(
    *,
    sub: str = PLATFORM_ADMIN_ID,
    tenant_id: str | None = None,
    roles: list[str] | None = None,
    scopes: list[str] | None = None,
    permissions: list[str] | None = None,
    exp_offset: int = 3600,
    iat_offset: int = 0,
    issuer: str = TEST_ISSUER,
    audience: str = TEST_AUDIENCE,
    secret: str = TEST_SECRET,
    algorithm: str = "HS256",
    extra: dict | None = None,
) -> str:
    """Generate a test JWT token."""
    now = int(time.time())
    payload = {
        "sub": sub,
        "iat": now + iat_offset,
        "exp": now + exp_offset,
        "iss": issuer,
        "aud": audience,
        "roles": roles or ["platform_admin"],
        "scopes": scopes or [],
    }
    if tenant_id:
        payload["tenant_id"] = tenant_id
    if permissions is not None:
        payload["permissions"] = permissions
    if extra:
        payload.update(extra)
    return jwt.encode(payload, secret, algorithm=algorithm)


@pytest.fixture
def auth_config() -> AuthConfig:
    """Create test auth configuration."""
    return AuthConfig(
        issuer=TEST_ISSUER,
        audience=TEST_AUDIENCE,
        verification_key=TEST_SECRET,
        algorithm="HS256",
        leeway_seconds=0,
        require_tenant=False,  # Platform admins may not have tenant_id
        public_paths=("/health",),
    )


@pytest.fixture
def rbac_policy() -> RbacPolicy:
    """Load RBAC policy from config file."""
    return RbacPolicy.from_yaml(RBAC_MATRIX)


@pytest.fixture
def event_publisher() -> InMemoryEventPublisher:
    """Create in-memory event publisher for testing."""
    return InMemoryEventPublisher()


@pytest_asyncio.fixture
async def db_manager() -> AsyncGenerator[DatabaseManager, None]:
    """Create in-memory SQLite database for testing."""
    # Use SQLite for fast in-memory testing
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    manager = DatabaseManager.__new__(DatabaseManager)
    manager.engine = engine
    manager.session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    yield manager
    
    # Cleanup
    await engine.dispose()


@pytest.fixture
def provisioning_service(event_publisher: InMemoryEventPublisher) -> TenantProvisioningService:
    """Create provisioning service with test event publisher."""
    return TenantProvisioningService(
        event_publisher=event_publisher,
        idempotency_ttl_hours=24,
    )


@pytest.fixture
def test_app(
    auth_config: AuthConfig,
    rbac_policy: RbacPolicy,
    db_manager: DatabaseManager,
    provisioning_service: TenantProvisioningService,
    event_publisher: InMemoryEventPublisher,
) -> Starlette:
    """Create test application with all dependencies injected."""
    app = create_app(auth_config=auth_config, rbac_policy=rbac_policy)
    
    # Override app state with test instances
    app.state.db_manager = db_manager
    app.state.provisioning_service = provisioning_service
    app.state.event_publisher = event_publisher
    
    return app


@pytest.fixture
def client(test_app: Starlette) -> TestClient:
    """Create test client for the application."""
    return TestClient(test_app, raise_server_exceptions=False)


@pytest.fixture
def platform_admin_token() -> str:
    """Generate token for platform admin."""
    return make_token(
        sub=PLATFORM_ADMIN_ID,
        roles=["platform_admin"],
    )


@pytest.fixture
def tenant_admin_token() -> str:
    """Generate token for tenant admin."""
    return make_token(
        sub=TENANT_ADMIN_ID,
        tenant_id=TEST_TENANT_ID,
        roles=["tenant_admin"],
    )


@pytest.fixture
def learner_token() -> str:
    """Generate token for learner."""
    return make_token(
        sub=LEARNER_ID,
        tenant_id=TEST_TENANT_ID,
        roles=["learner"],
    )
