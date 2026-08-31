"""Shared fixtures for tenant provisioning integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from asiwdp_auth import AuthConfig, RbacPolicy
from asiwdp_tenant_provisioning.app import create_app
from asiwdp_tenant_provisioning.events import InMemoryEventBus
from asiwdp_tenant_provisioning.repository import TenantRepository

from .helpers import TEST_AUDIENCE, TEST_ISSUER, TEST_SECRET, make_token

REPO_ROOT = Path(__file__).resolve().parents[3]
RBAC_MATRIX = REPO_ROOT / "config" / "rbac" / "role-permission-matrix.yaml"


@pytest.fixture
def auth_config() -> AuthConfig:
    return AuthConfig(
        issuer=TEST_ISSUER,
        audience=TEST_AUDIENCE,
        verification_key=TEST_SECRET,
        algorithm="HS256",
        leeway_seconds=0,
        require_tenant=True,
        public_paths=("/health",),
    )


@pytest.fixture
def rbac_policy() -> RbacPolicy:
    return RbacPolicy.from_yaml(RBAC_MATRIX)


@pytest.fixture
def repository() -> TenantRepository:
    return TenantRepository(":memory:")


@pytest.fixture
def event_bus() -> InMemoryEventBus:
    return InMemoryEventBus()


@pytest.fixture
def client(
    auth_config: AuthConfig,
    rbac_policy: RbacPolicy,
    repository: TenantRepository,
    event_bus: InMemoryEventBus,
) -> TestClient:
    app = create_app(
        auth_config=auth_config,
        rbac_policy=rbac_policy,
        repository=repository,
        event_bus=event_bus,
    )
    return TestClient(app)


@pytest.fixture
def platform_admin_headers() -> dict[str, str]:
    token = make_token(roles=["PlatformAdmin"])
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def platform_admin_snake_headers() -> dict[str, str]:
    token = make_token(roles=["platform_admin"])
    return {"Authorization": f"Bearer {token}"}
