"""Starlette application factory for tenant provisioning service."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from starlette.applications import Starlette
from starlette.middleware import Middleware

from asiwdp_auth import AuthConfig, AuthMiddleware, RbacPolicy
from tenant_provisioning.config import config
from tenant_provisioning.database import DatabaseManager
from tenant_provisioning.events import create_event_publisher
from tenant_provisioning.routes import routes
from tenant_provisioning.service import TenantProvisioningService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: Starlette) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup/shutdown."""
    logger.info("Starting tenant provisioning service...")

    # Initialize database
    db_manager = DatabaseManager(config.database_url)
    app.state.db_manager = db_manager

    # Initialize event publisher
    event_publisher = create_event_publisher(
        config.event_bus_url if config.event_bus_url else None,
        config.event_bus_topic,
    )
    app.state.event_publisher = event_publisher

    # Initialize provisioning service
    app.state.provisioning_service = TenantProvisioningService(
        event_publisher=event_publisher,
        idempotency_ttl_hours=config.idempotency_ttl_hours,
    )

    logger.info("Tenant provisioning service started")
    yield

    # Cleanup
    logger.info("Shutting down tenant provisioning service...")
    await event_publisher.close()
    await db_manager.close()
    logger.info("Tenant provisioning service stopped")


def create_app(
    auth_config: AuthConfig | None = None,
    rbac_policy: RbacPolicy | None = None,
) -> Starlette:
    """Create and configure the Starlette application.
    
    Args:
        auth_config: Optional auth configuration (uses env config if not provided)
        rbac_policy: Optional RBAC policy (loads from file if not provided)
    
    Returns:
        Configured Starlette application
    """
    # Load auth config from environment if not provided
    if auth_config is None:
        auth_config = AuthConfig(
            issuer=config.auth_issuer,
            audience=config.auth_audience,
            verification_key=config.auth_verification_key,
            algorithm=config.auth_algorithm,
            require_tenant=False,  # Platform admins may not have tenant_id
            public_paths=config.public_paths,
        )

    # Load RBAC policy if not provided
    if rbac_policy is None:
        rbac_policy = RbacPolicy.from_yaml(config.rbac_matrix_path)

    # Configure authentication middleware
    middleware = [
        Middleware(
            AuthMiddleware,
            config=auth_config,
            policy=rbac_policy,
        ),
    ]

    app = Starlette(
        debug=False,
        routes=routes,
        middleware=middleware,
        lifespan=lifespan,
    )

    return app


# Default application instance
app = create_app()
