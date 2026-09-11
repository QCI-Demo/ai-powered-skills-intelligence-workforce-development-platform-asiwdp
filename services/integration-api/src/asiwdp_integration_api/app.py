"""FastAPI application factory for the Integration API service."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI

from asiwdp_integration_api.router import v1_router, v2_router

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
    """Build the ASGI app with JWT auth, tenant context, and X-API-Version."""
    app = FastAPI(
        title="ASIWDP Integration API Service",
        version="0.1.0",
        description=(
            "Secured versioned REST APIs for HRIS, LMS, and content-provider "
            "bidirectional exchange. Enforces tenant-scoped OAuth2/JWT scopes "
            "and returns X-API-Version on every response."
        ),
    )
    app.include_router(v1_router, prefix="/api")
    app.include_router(v2_router, prefix="/api")

    @app.get("/health", tags=["Health"])
    def root_health() -> dict[str, str]:
        return {"status": "ok", "service": "integration-api"}

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
        _mount_security(
            app, auth_config=auth_config, rbac_matrix_path=rbac_matrix_path
        )
    else:
        # Still stamp X-API-Version when auth is disabled for local scaffolding
        from asiwdp_auth import ApiVersionMiddleware

        app.add_middleware(
            ApiVersionMiddleware,
            default_version="v1",
            supported_versions=("v1", "v2"),
        )

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


def _mount_security(
    app: FastAPI,
    *,
    auth_config: "AuthConfig | None" = None,
    rbac_matrix_path: str | Path | None = None,
) -> None:
    from asiwdp_auth import ApiVersionMiddleware, AuthConfig, AuthMiddleware

    matrix = Path(rbac_matrix_path) if rbac_matrix_path else _default_matrix_path()
    base = auth_config or AuthConfig.from_env()
    public = tuple(
        dict.fromkeys(
            list(base.public_paths)
            + [
                "/health",
                "/api/v1/health",
                "/api/v2/health",
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
        require_tenant=True,
        public_paths=public,
        default_required_permissions=(),
    )
    # Starlette: last added = outermost. Version header must wrap auth so 401s
    # also receive X-API-Version.
    app.add_middleware(
        AuthMiddleware,
        config=config,
        rbac_matrix_path=str(matrix),
        map_tenant_context=True,
    )
    app.add_middleware(
        ApiVersionMiddleware,
        default_version="v1",
        supported_versions=("v1", "v2"),
    )


def _module_app() -> FastAPI:
    try:
        return create_app()
    except ValueError:
        return create_app(enable_auth=False)


app = _module_app()
