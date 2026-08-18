"""FastAPI application factory for the Skills Framework service."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI

from asiwdp_skills_framework.router import api_router
from asiwdp_skills_framework.store import TaxonomyStore


def create_app(*, enable_auth: bool | None = None) -> FastAPI:
    """
    Build the ASGI application.

    Auth middleware is enabled when ``ASIWDP_AUTH_ENABLED=true`` (or
    ``enable_auth=True``) and the shared RBAC matrix is available.
    """
    app = FastAPI(
        title="ASIWDP Skills Framework Service",
        version="1.0.0",
        description=(
            "Versioned CRUD APIs for skills, categories, and proficiency levels, "
            "with bulk import/export pipelines and tenant isolation."
        ),
    )
    app.state.taxonomy_store = TaxonomyStore()
    app.include_router(api_router, prefix="/api/v1")

    auth_flag = (
        enable_auth
        if enable_auth is not None
        else os.getenv("ASIWDP_AUTH_ENABLED", "false").lower() in {"1", "true", "yes"}
    )
    if auth_flag:
        _mount_auth(app)

    return app


def _mount_auth(app: FastAPI) -> None:
    from asiwdp_auth import AuthConfig, AuthMiddleware

    matrix = Path(__file__).resolve().parents[4] / "config" / "rbac" / "role-permission-matrix.yaml"
    if not matrix.exists():
        # Fallback when installed as a package outside the monorepo layout
        matrix = Path(os.getenv("ASIWDP_RBAC_MATRIX", "config/rbac/role-permission-matrix.yaml"))

    base = AuthConfig.from_env()
    # Health and OpenAPI docs remain public
    public = tuple(
        dict.fromkeys(
            list(base.public_paths)
            + ["/api/v1/health", "/health", "/docs", "/openapi.json", "/redoc"]
        )
    )
    config = AuthConfig(
        issuer=base.issuer,
        audience=base.audience,
        verification_key=base.verification_key,
        algorithm=base.algorithm,
        leeway_seconds=base.leeway_seconds,
        require_tenant=base.require_tenant,
        public_paths=public,
        default_required_permissions=base.default_required_permissions,
    )
    app.add_middleware(
        AuthMiddleware,
        config=config,
        rbac_matrix_path=str(matrix),
    )
