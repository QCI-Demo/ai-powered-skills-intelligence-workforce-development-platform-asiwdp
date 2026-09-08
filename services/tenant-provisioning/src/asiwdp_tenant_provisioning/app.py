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


def create_app(
    *,
    enable_auth: bool | None = None,
    auth_config: "AuthConfig | None" = None,
    rbac_matrix_path: str | Path | None = None,
) -> FastAPI:
    """
    Build the ASGI application.

    Auth middleware (Story S2) is enabled when ``ASIWDP_AUTH_ENABLED=true``,
    ``enable_auth=True``, or an explicit ``auth_config`` is provided.
    """
    app = FastAPI(
        title="ASIWDP Tenant Provisioning Service",
        version="1.0.0",
        description=(
            "Idempotent tenant provisioning with default configuration, "
            "PlatformAdmin RBAC, and tenant-scoped telemetry events."
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
            else os.getenv("ASIWDP_AUTH_ENABLED", "false").lower()
            in {"1", "true", "yes"}
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


app = create_app()
