"""Tests for tenant context mapping, scope enforcement, and X-API-Version."""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from asiwdp_auth import (
    API_VERSION_HEADER,
    ApiVersionMiddleware,
    AuthConfig,
    AuthMiddleware,
    require_scope,
    resolve_api_version,
)
from asiwdp_auth.rbac import RbacPolicy
from asiwdp_auth.tenant_context import TenantContext, get_tenant_context
from tests.conftest import RBAC_MATRIX, make_token


def test_resolve_api_version_from_path() -> None:
    assert resolve_api_version("/api/v1/hris/employees") == "v1"
    assert resolve_api_version("/api/v2/lms/activities") == "v2"
    assert resolve_api_version("/health", default="v1") == "v1"


def test_resolve_api_version_from_header() -> None:
    assert (
        resolve_api_version("/integrations/sync", request_header="v2", default="v1")
        == "v2"
    )
    assert (
        resolve_api_version("/integrations/sync", request_header="2", default="v1")
        == "v2"
    )


def test_tenant_context_scope_checks() -> None:
    ctx = TenantContext(
        tenant_id="22222222-2222-2222-2222-222222222222",
        subject="11111111-1111-1111-1111-111111111111",
        scopes=("hris:write",),
        roles=("service_account",),
        effective_permissions=frozenset({"hris:write", "progress:read"}),
    )
    assert ctx.has_scope("hris:write")
    assert not ctx.has_scope("lms:write")
    ctx.require_scopes("hris:write")


def _build_client() -> TestClient:
    @require_scope("hris:write")
    async def ingest_employee(request: Request) -> JSONResponse:
        tenant = get_tenant_context(request)
        return JSONResponse(
            {
                "ok": True,
                "tenant_id": tenant.tenant_id,
                "scopes": list(tenant.scopes),
            }
        )

    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "up"})

    app = Starlette(
        routes=[
            Route("/health", health),
            Route("/api/v1/hris/employees", ingest_employee, methods=["POST"]),
            Route("/api/v2/hris/employees", ingest_employee, methods=["POST"]),
        ]
    )
    config = AuthConfig(
        issuer="https://auth.asiwdp.test/",
        audience="asiwdp-api",
        verification_key="test-only-hs256-secret-not-for-production",
        algorithm="HS256",
        leeway_seconds=0,
        require_tenant=True,
        public_paths=("/health",),
    )
    policy = RbacPolicy.from_yaml(RBAC_MATRIX)
    # Outer middleware runs first on the way in for Starlette/FastAPI add_middleware
    app.add_middleware(AuthMiddleware, config=config, policy=policy)
    app.add_middleware(
        ApiVersionMiddleware,
        default_version="v1",
        supported_versions=("v1", "v2"),
    )
    return TestClient(app)


class TestTenantContextAndScopes:
    def test_maps_claims_to_tenant_context(self) -> None:
        client = _build_client()
        token = make_token(
            roles=["service_account"],
            scopes=["hris:write"],
        )
        response = client.post(
            "/api/v1/hris/employees",
            headers={"Authorization": f"Bearer {token}"},
            json={"sourceRecordId": "E-1"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["tenant_id"] == "22222222-2222-2222-2222-222222222222"
        assert "hris:write" in body["scopes"]

    def test_missing_scope_returns_403(self) -> None:
        client = _build_client()
        token = make_token(roles=["learner"], scopes=["skills:read"])
        response = client.post(
            "/api/v1/hris/employees",
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        assert response.status_code == 403
        assert response.json()["error"] == "scope_denied"


class TestApiVersionHeader:
    def test_v1_response_includes_version_header(self) -> None:
        client = _build_client()
        token = make_token(roles=["service_account"], scopes=["hris:write"])
        response = client.post(
            "/api/v1/hris/employees",
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        assert response.status_code == 200
        assert response.headers.get(API_VERSION_HEADER) == "v1"

    def test_v2_response_includes_version_header(self) -> None:
        client = _build_client()
        token = make_token(roles=["service_account"], scopes=["hris:write"])
        response = client.post(
            "/api/v2/hris/employees",
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        assert response.status_code == 200
        assert response.headers.get(API_VERSION_HEADER) == "v2"

    def test_public_health_still_gets_version_header(self) -> None:
        client = _build_client()
        response = client.get("/health")
        assert response.status_code == 200
        assert response.headers.get(API_VERSION_HEADER) == "v1"
