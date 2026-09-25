"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from tenant_provisioning.config import get_settings
from tenant_provisioning.router import router

# Configure structured logging
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan management."""
    settings = get_settings()
    logger.info(
        "Starting tenant provisioning service",
        service=settings.service_name,
        version=settings.service_version,
        environment=settings.environment,
    )
    yield
    logger.info("Shutting down tenant provisioning service")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="ASIWDP Tenant Provisioning Service",
        description=(
            "Idempotent REST endpoints for tenant provisioning with "
            "default configuration and event publishing."
        ),
        version=settings.service_version,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # Add auth middleware if rbac matrix exists
    rbac_path = Path(settings.rbac_matrix_path)
    if rbac_path.exists():
        try:
            from asiwdp_auth.config import AuthConfig
            from asiwdp_auth.middleware import AuthMiddleware

            auth_config = AuthConfig(
                issuer=settings.jwt_issuer,
                audience=settings.jwt_audience,
                algorithms=settings.jwt_algorithms,
                jwks_url=settings.jwks_url,
                public_paths=["/health", "/docs", "/redoc", "/openapi.json"],
            )
            app = AuthMiddleware(
                app,
                config=auth_config,
                rbac_matrix_path=rbac_path,
            )
            logger.info("Auth middleware enabled", rbac_matrix=str(rbac_path))
        except ImportError:
            logger.warning("asiwdp-auth not installed, auth middleware disabled")
    else:
        logger.warning("RBAC matrix not found, auth middleware disabled", path=str(rbac_path))

    # Health endpoint (public, no auth)
    @app.get("/health", tags=["Health"])
    async def health_check() -> dict[str, str]:
        """Liveness probe endpoint."""
        return {"status": "healthy", "service": settings.service_name}

    # Include routers
    app.include_router(router)

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle unexpected exceptions."""
        logger.exception("Unhandled exception", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "message": "An unexpected error occurred",
            },
        )

    return app


# Application instance for uvicorn
app = create_app()


def main() -> None:
    """Entry point for CLI."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "tenant_provisioning.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
