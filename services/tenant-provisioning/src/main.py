"""FastAPI application entry point for tenant provisioning service."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting tenant provisioning service")
    yield
    logger.info("Shutting down tenant provisioning service")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="ASIWDP Tenant Provisioning Service",
        description="""
Automated tenant provisioning and configuration service for the 
AI-Powered Skills Intelligence & Workforce Development Platform (ASIWDP).

## Features

- **Idempotent Provisioning**: Create tenants with replay protection
- **Default Configuration**: Tier-based configuration initialization
- **RBAC Protection**: PlatformAdmin role required for tenant creation
- **Event Telemetry**: Provisioning events for downstream services

## Authentication

All endpoints (except /health) require OAuth2/JWT Bearer authentication.
See the asiwdp-auth middleware documentation for claim schema.
        """,
        version="1.0.0",
        lifespan=lifespan,
    )

    # Add auth middleware
    rbac_path = Path(__file__).parent.parent.parent.parent / "config" / "rbac" / "role-permission-matrix.yaml"
    if rbac_path.exists():
        try:
            from asiwdp_auth import AuthConfig, AuthMiddleware

            config = AuthConfig.from_env()
            app.add_middleware(
                AuthMiddleware,
                config=config,
                rbac_matrix_path=str(rbac_path),
            )
            logger.info("Auth middleware configured with RBAC matrix")
        except Exception as exc:
            logger.warning("Auth middleware not configured: %s", exc)
    else:
        logger.warning("RBAC matrix not found at %s", rbac_path)

    # Import and include routers
    from src.controllers.tenant_controller import router

    app.include_router(router)

    # Health check endpoint
    @app.get("/health", tags=["Health"])
    async def health_check():
        return {"status": "healthy", "service": "tenant-provisioning"}

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled exception: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "message": "An unexpected error occurred",
            },
        )

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
