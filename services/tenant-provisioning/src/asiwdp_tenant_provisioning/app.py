"""FastAPI application: POST /api/tenants with auth, RBAC, and idempotency."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.middleware import Middleware

from asiwdp_auth import AuthConfig, AuthMiddleware, RbacPolicy
from asiwdp_auth.errors import AuthorizationError

from asiwdp_tenant_provisioning.events import InMemoryEventBus
from asiwdp_tenant_provisioning.rbac import assert_platform_admin
from asiwdp_tenant_provisioning.repository import ConflictError, TenantRepository
from asiwdp_tenant_provisioning.schemas import TenantCreateRequest
from asiwdp_tenant_provisioning.service import TenantProvisioningService

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_RBAC = _REPO_ROOT / "config" / "rbac" / "role-permission-matrix.yaml"


def create_app(
    *,
    auth_config: AuthConfig | None = None,
    rbac_policy: RbacPolicy | None = None,
    repository: TenantRepository | None = None,
    event_bus: InMemoryEventBus | None = None,
    rbac_matrix_path: str | Path | None = None,
) -> FastAPI:
    """Build the tenant provisioning ASGI app.

    Auth middleware from Story S2 is applied globally; the create endpoint
    additionally requires the PlatformAdmin role.
    """
    repo = repository or TenantRepository(":memory:")
    bus = event_bus or InMemoryEventBus()
    service = TenantProvisioningService(repo, bus)

    config = auth_config or AuthConfig.from_env()
    if rbac_policy is None:
        matrix = Path(rbac_matrix_path) if rbac_matrix_path else _DEFAULT_RBAC
        policy = RbacPolicy.from_yaml(matrix)
    else:
        policy = rbac_policy

    # Public health only — all other routes require JWT via AuthMiddleware.
    middleware = [
        Middleware(
            AuthMiddleware,
            config=config,
            policy=policy,
        )
    ]

    app = FastAPI(
        title="ASIWDP Tenant Provisioning Service",
        version="0.1.0",
        middleware=middleware,
    )
    app.state.repository = repo
    app.state.event_bus = bus
    app.state.provisioning_service = service
    app.state.auth_config = config
    app.state.rbac_policy = policy

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "up"}

    @app.post("/api/tenants")
    async def create_tenant(
        request: Request,
        idempotency_key: str | None = Header(
            default=None, alias="Idempotency-Key"
        ),
        x_correlation_id: str | None = Header(
            default=None, alias="X-Correlation-Id"
        ),
    ) -> JSONResponse:
        principal = getattr(request.state, "principal", None)
        if principal is None:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "token_missing",
                    "message": "Unauthenticated request",
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            assert_platform_admin(principal)
        except AuthorizationError as exc:
            return JSONResponse(
                status_code=403,
                content={"error": exc.error_code, "message": exc.message},
            )

        try:
            raw: Any = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_json",
                    "message": "Request body must be valid JSON",
                },
            )

        try:
            payload = TenantCreateRequest.model_validate(raw)
        except ValidationError as exc:
            details = exc.errors(include_url=False, include_context=False)
            return JSONResponse(
                status_code=422,
                content={
                    "error": "validation_error",
                    "message": "Payload failed schema validation",
                    "details": details,
                },
            )

        key = idempotency_key.strip() if idempotency_key else None
        if key == "":
            key = None

        try:
            response, status = service.provision(
                payload,
                principal=principal,
                idempotency_key=key,
                correlation_id=x_correlation_id,
            )
        except ConflictError as exc:
            return JSONResponse(
                status_code=409,
                content={"error": "conflict", "message": exc.message},
            )

        return JSONResponse(
            status_code=status,
            content=response.model_dump(mode="json"),
        )

    return app
