"""Starlette application for tenant provisioning service.

Task: 78cab998-3bb5-4262-bc80-e2160bdc2805 - Add route to API gateway
Task: ca4babed-4042-4c03-97bc-9705218cbfc9 - Apply middleware from Story S2
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from tenant_provisioning.config import ServiceConfig
from tenant_provisioning.database import TenantRepository, create_engine_and_session
from tenant_provisioning.events import EventPublisher, HttpEventPublisher, LoggingEventPublisher
from tenant_provisioning.service import TenantProvisioningService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def health_endpoint(request: Request) -> JSONResponse:
    """Health check endpoint (unauthenticated)."""
    return JSONResponse({"status": "healthy", "service": "tenant-provisioning"})


def create_app(
    config: ServiceConfig | None = None,
    repository: TenantRepository | None = None,
    event_publisher: EventPublisher | None = None,
) -> Starlette:
    """Create the Starlette application.
    
    Task: 78cab998-3bb5-4262-bc80-e2160bdc2805 - Add route to API gateway
    Task: ca4babed-4042-4c03-97bc-9705218cbfc9 - Apply middleware from Story S2
    """
    if config is None:
        config = ServiceConfig.from_env()

    # Create database repository
    if repository is None:
        session_factory = create_engine_and_session(config.database_url)
        repository = TenantRepository(session_factory)

    # Create event publisher
    if event_publisher is None:
        if config.debug:
            event_publisher = LoggingEventPublisher()
        else:
            event_publisher = HttpEventPublisher(config.event_bus_url)

    # Create service
    service = TenantProvisioningService(
        repository=repository,
        event_publisher=event_publisher,
        idempotency_ttl_hours=config.idempotency_ttl_hours,
    )

    # Define routes
    # Task: 78cab998-3bb5-4262-bc80-e2160bdc2805
    routes = [
        Route("/health", health_endpoint, methods=["GET"]),
        Route("/api/tenants", service.create_tenant, methods=["POST"]),
    ]

    # Create app
    app = Starlette(routes=routes, debug=config.debug)

    # Apply authentication middleware from Story S2
    # Task: ca4babed-4042-4c03-97bc-9705218cbfc9
    try:
        from asiwdp_auth import AuthConfig, AuthMiddleware, RbacPolicy

        auth_config = AuthConfig(
            issuer=config.jwt_issuer,
            audience=config.jwt_audience,
            jwks_url=config.jwks_url,
            public_paths=["/health"],
        )

        # Load RBAC policy
        rbac_matrix_path = config.rbac_matrix_path
        if rbac_matrix_path.exists():
            policy = RbacPolicy.from_yaml(rbac_matrix_path)
        else:
            logger.warning(
                "RBAC matrix not found at %s, using minimal policy",
                rbac_matrix_path,
            )
            policy = RbacPolicy.from_dict({
                "version": "1.0.0",
                "roles": {
                    "platform_admin": {
                        "platform_scoped": True,
                        "permissions": ["*"],
                    }
                },
            })

        app = AuthMiddleware(
            app,
            config=auth_config,
            policy=policy,
        )
        logger.info("Applied authentication middleware from Story S2")
    except ImportError:
        logger.warning(
            "asiwdp-auth not installed, running without authentication middleware"
        )
    except Exception as e:
        logger.error("Failed to apply auth middleware: %s", e)
        raise

    return app


# Application instance for ASGI servers
app = create_app()


if __name__ == "__main__":
    import uvicorn

    config = ServiceConfig.from_env()
    uvicorn.run(
        "tenant_provisioning.app:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
    )
