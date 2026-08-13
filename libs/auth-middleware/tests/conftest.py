"""Shared fixtures for asiwdp-auth tests."""

from __future__ import annotations

import time
from pathlib import Path

import jwt
import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from asiwdp_auth import AuthConfig, AuthMiddleware, require_permission
from asiwdp_auth.rbac import RbacPolicy

REPO_ROOT = Path(__file__).resolve().parents[3]
RBAC_MATRIX = REPO_ROOT / "config" / "rbac" / "role-permission-matrix.yaml"

TEST_SECRET = "test-only-hs256-secret-not-for-production"
TEST_ISSUER = "https://auth.asiwdp.test/"
TEST_AUDIENCE = "asiwdp-api"


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


def make_token(
    *,
    sub: str = "11111111-1111-1111-1111-111111111111",
    tenant_id: str = "22222222-2222-2222-2222-222222222222",
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
    now = int(time.time())
    payload = {
        "sub": sub,
        "tenant_id": tenant_id,
        "iat": now + iat_offset,
        "exp": now + exp_offset,
        "iss": issuer,
        "aud": audience,
        "roles": roles or ["learner"],
        "scopes": scopes or [],
    }
    if permissions is not None:
        payload["permissions"] = permissions
    if extra:
        payload.update(extra)
    return jwt.encode(payload, secret, algorithm=algorithm)


async def _protected(request: Request) -> JSONResponse:
    principal = request.state.principal
    return JSONResponse(
        {
            "ok": True,
            "subject": principal.subject,
            "tenant_id": principal.tenant_id,
            "roles": list(principal.roles),
            "permissions": sorted(principal.effective_permissions),
        }
    )


@require_permission("skills:write")
async def _skills_write(request: Request) -> JSONResponse:
    return JSONResponse({"ok": True, "action": "skills:write"})


async def _health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "up"})


@pytest.fixture
def app_client(auth_config: AuthConfig, rbac_policy: RbacPolicy) -> TestClient:
    app = Starlette(
        routes=[
            Route("/health", _health),
            Route("/api/me", _protected),
            Route("/api/skills", _skills_write, methods=["POST"]),
        ]
    )
    app.add_middleware(
        AuthMiddleware,
        config=auth_config,
        policy=rbac_policy,
    )
    return TestClient(app)


@pytest.fixture
def rbac_app_client(auth_config: AuthConfig, rbac_policy: RbacPolicy) -> TestClient:
    """App that requires skills:admin at middleware level for all protected routes."""
    app = Starlette(routes=[Route("/api/admin", _protected)])
    app.add_middleware(
        AuthMiddleware,
        config=auth_config,
        policy=rbac_policy,
        required_permissions=("skills:admin",),
    )
    return TestClient(app)
