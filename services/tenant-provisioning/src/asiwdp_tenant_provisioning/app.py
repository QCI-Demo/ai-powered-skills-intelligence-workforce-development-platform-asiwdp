"""FastAPI application factory for the Tenant Provisioning service."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI

from asiwdp_tenant_provisioning.events.publisher import InMemoryEventBus
from asiwdp_tenant_provisioning.router import api_router
from asiwdp_tenant_provisioning.store import InMemoryTenantStore

if TYPE_CHECKING:
    from asiwdp_auth import AuthConfig


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def create_app(
    *,
    enable_auth: bool | None = None,
    auth_config: "AuthConfig | None" = None,
    rbac_matrix_path: str | Path | None = None,
) -> FastAPI:
    """
    Build the ASGI application.

    Story S2 ``AuthMiddleware`` is mounted by default so ``POST /api/tenants``
    rejects unauthenticated callers. Disable only via ``enable_auth=False`` or
    ``ASIWDP_AUTH_ENABLED=false`` (local scaffolding). Route-level
    ``require_platform_admin`` still returns 401/403 when a principal is absent
    or lacks ``PlatformAdmin``.
    """
    app = FastAPI(
        title="ASIWDP Tenant Provisioning Service",
        version="1.0.0",
        description=(
            "Idempotent tenant provisioning with default configuration, "
            "PlatformAdmin RBAC (Story S2 middleware), and tenant-scoped telemetry."
        ),
    )
    app.state.tenant_store = InMemoryTenantStore()
    app.state.event_bus = InMemoryEventBus()
    app.include_router(api_router, prefix="/api")

    auth_flag = (
        True
        if auth_config is not None
        else (
            enable_auth
            if enable_auth is not None
            else _env_flag("ASIWDP_AUTH_ENABLED", default=True)
        )
    )
    if auth_flag:
        _mount_auth(app, auth_config=auth_config, rbac_matrix_path=rbac_matrix_path)

    return app


def _default_matrix_path() -> Path:
    matrix = (
        Path(__file__).resolve().parents[4]
        / "config"
        / "rbac"
        / "role-permission-matrix.yaml"
    )
    if matrix.exists():
        return matrix
    return Path(
        os.getenv("ASIWDP_RBAC_MATRIX", "config/rbac/role-permission-matrix.yaml")
    )


def _mount_auth(
    app: FastAPI,
    *,
    auth_config: "AuthConfig | None" = None,
    rbac_matrix_path: str | Path | None = None,
) -> None:
    from asiwdp_auth import AuthConfig, AuthMiddleware

    matrix = Path(rbac_matrix_path) if rbac_matrix_path else _default_matrix_path()
    base = auth_config or AuthConfig.from_env()
    # Platform admins may omit tenant_id on break-glass tokens; route still audits it.
    public = tuple(
        dict.fromkeys(
            list(base.public_paths)
            + [
                "/api/tenants/health",
                "/health",
                "/docs",
                "/openapi.json",
                "/redoc",
            ]
        )
    )
    config = AuthConfig(
        issuer=base.issuer,
        audience=base.audience,
        verification_key=base.verification_key,
        algorithm=base.algorithm,
        leeway_seconds=base.leeway_seconds,
        require_tenant=False,
        public_paths=public,
        default_required_permissions=(),
    )
    app.add_middleware(
        AuthMiddleware,
        config=config,
        rbac_matrix_path=str(matrix),
    )


def _module_app() -> FastAPI:
    """
    ASGI entrypoint for uvicorn.

    Auth is on by default when ``ASIWDP_AUTH_*`` is configured. If secrets are
    absent (package import / local scaffolding), fall back to middleware-off
    with route-level fail-closed PlatformAdmin checks (401 without principal).
    Production must set ``ASIWDP_AUTH_ISSUER``, ``ASIWDP_AUTH_AUDIENCE``, and
    ``ASIWDP_AUTH_VERIFICATION_KEY``.
    """
    try:
        return create_app()
    except ValueError:
        return create_app(enable_auth=False)


app = _module_app()
