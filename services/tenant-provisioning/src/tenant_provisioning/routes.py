"""API routes for tenant provisioning."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from asiwdp_auth import require_permission
from tenant_provisioning.models import CreateTenantRequest, ErrorResponse
from tenant_provisioning.service import (
    IdempotencyConflictError,
    TenantExistsError,
    TenantNotFoundError,
    TenantProvisioningService,
)

if TYPE_CHECKING:
    from tenant_provisioning.database import DatabaseManager

logger = logging.getLogger(__name__)


def get_db_manager(request: Request) -> "DatabaseManager":
    """Get database manager from app state."""
    return request.app.state.db_manager


def get_provisioning_service(request: Request) -> TenantProvisioningService:
    """Get provisioning service from app state."""
    return request.app.state.provisioning_service


def get_client_info(request: Request) -> tuple[str | None, str | None]:
    """Extract client IP and user agent from request."""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return ip_address, user_agent


async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint (unauthenticated)."""
    return JSONResponse({"status": "healthy", "service": "tenant-provisioning"})


@require_permission("tenants:admin")
async def create_tenant(request: Request) -> JSONResponse:
    """Create a new tenant (POST /api/tenants).
    
    This endpoint is secured with RBAC and requires the `tenants:admin` permission,
    which is granted to the `platform_admin` role.
    
    Supports idempotency via the `Idempotency-Key` header.
    """
    # Get authenticated principal
    principal = request.state.principal
    
    # Validate platform admin role (additional check for security)
    if not principal.has_role("platform_admin") and "*" not in principal.effective_permissions:
        logger.warning(
            "Non-platform_admin attempted tenant creation: subject=%s roles=%s",
            principal.subject,
            principal.roles,
        )
        return JSONResponse(
            status_code=403,
            content=ErrorResponse(
                error="forbidden",
                message="Only platform administrators can create tenants",
            ).model_dump(),
        )

    # Parse and validate request body
    try:
        body = await request.json()
        tenant_request = CreateTenantRequest.model_validate(body)
    except ValidationError as e:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                error="validation_error",
                message="Invalid request body",
                details={"errors": e.errors()},
            ).model_dump(),
        )
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                error="invalid_json",
                message=f"Failed to parse request body: {e}",
            ).model_dump(),
        )

    # Get idempotency key
    idempotency_key = request.headers.get("Idempotency-Key")
    
    # Get client info for audit
    ip_address, user_agent = get_client_info(request)

    # Get services
    db_manager = get_db_manager(request)
    service = get_provisioning_service(request)

    try:
        async with await db_manager.get_session() as session:
            response = await service.create_tenant(
                session=session,
                request=tenant_request,
                created_by=UUID(principal.subject),
                actor_type=principal.actor_type,
                idempotency_key=idempotency_key,
                ip_address=ip_address,
                user_agent=user_agent,
            )

        return JSONResponse(
            status_code=201,
            content=response.model_dump(mode="json"),
            headers={"X-Tenant-Id": str(response.id)},
        )

    except TenantExistsError as e:
        return JSONResponse(
            status_code=409,
            content=ErrorResponse(
                error="conflict",
                message=str(e),
                details={"slug": e.slug},
            ).model_dump(),
        )

    except IdempotencyConflictError as e:
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error="idempotency_conflict",
                message=str(e),
                details={"idempotency_key": e.idempotency_key},
            ).model_dump(),
        )

    except Exception as e:
        logger.exception("Failed to create tenant")
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="internal_error",
                message="Failed to provision tenant",
            ).model_dump(),
        )


@require_permission("tenants:read")
async def get_tenant(request: Request) -> JSONResponse:
    """Get tenant by ID (GET /api/tenants/{tenant_id}).
    
    Platform admins can read any tenant; others can only read their own tenant.
    """
    principal = request.state.principal
    tenant_id_str = request.path_params.get("tenant_id")

    try:
        tenant_id = UUID(tenant_id_str)
    except (ValueError, TypeError):
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                error="invalid_parameter",
                message="Invalid tenant_id format",
            ).model_dump(),
        )

    # Non-platform admins can only access their own tenant
    is_platform_admin = principal.has_role("platform_admin") or "*" in principal.effective_permissions
    if not is_platform_admin and principal.tenant_id and UUID(principal.tenant_id) != tenant_id:
        return JSONResponse(
            status_code=403,
            content=ErrorResponse(
                error="forbidden",
                message="Cannot access other tenant's data",
            ).model_dump(),
        )

    db_manager = get_db_manager(request)
    service = get_provisioning_service(request)

    try:
        async with await db_manager.get_session() as session:
            response = await service.get_tenant(session, tenant_id)

        return JSONResponse(
            status_code=200,
            content=response.model_dump(mode="json"),
        )

    except TenantNotFoundError:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error="not_found",
                message=f"Tenant {tenant_id} not found",
            ).model_dump(),
        )

    except Exception as e:
        logger.exception("Failed to get tenant")
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="internal_error",
                message="Failed to retrieve tenant",
            ).model_dump(),
        )


# Route definitions
routes = [
    Route("/health", health_check, methods=["GET"]),
    Route("/api/tenants", create_tenant, methods=["POST"]),
    Route("/api/tenants/{tenant_id:str}", get_tenant, methods=["GET"]),
]
