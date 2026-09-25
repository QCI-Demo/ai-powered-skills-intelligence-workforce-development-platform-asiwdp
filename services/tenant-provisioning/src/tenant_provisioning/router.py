"""FastAPI router for tenant provisioning endpoints."""

from __future__ import annotations

import logging
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from tenant_provisioning.database import get_session
from tenant_provisioning.idempotency import IdempotencyConflictError
from tenant_provisioning.models import (
    ConfigCategory,
    CreateTenantRequest,
    CreateTenantResponse,
    ErrorResponse,
    TenantConfigurationResponse,
    TenantResponse,
)
from tenant_provisioning.service import TenantExistsError, TenantProvisioningService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tenants", tags=["Tenants"])


# ---------------------------------------------------------------------------
# Authentication and Authorization Dependencies
# ---------------------------------------------------------------------------


def get_principal(request: Request) -> Any:
    """Extract authenticated principal from request state.

    The principal is set by the AuthMiddleware from Story S2.
    """
    principal = getattr(request.state, "principal", None)
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthenticated", "message": "Missing authentication"},
        )
    return principal


def require_platform_admin(principal: Any = Depends(get_principal)) -> Any:
    """Require PlatformAdmin role for tenant provisioning.

    Only platform administrators can create new tenants.
    This enforces RBAC from the role-permission-matrix.yaml.
    """
    effective_permissions = getattr(principal, "effective_permissions", frozenset())

    # Platform admin has "*" permission (wildcard)
    if "*" in effective_permissions:
        return principal

    # Check for specific tenant admin permission
    if "tenants:admin" in effective_permissions:
        return principal

    # Check roles directly
    roles = getattr(principal, "roles", ()) or ()
    if "platform_admin" in roles:
        return principal

    logger.warning(
        "Authorization denied for tenant provisioning",
        extra={
            "subject": getattr(principal, "subject", "unknown"),
            "roles": list(roles),
            "permissions": list(effective_permissions)[:10],
        },
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": "forbidden",
            "message": "PlatformAdmin role required for tenant provisioning",
        },
    )


def get_provisioning_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TenantProvisioningService:
    """Dependency for provisioning service."""
    return TenantProvisioningService(session)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=CreateTenantResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Tenant created successfully"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        401: {"model": ErrorResponse, "description": "Unauthenticated"},
        403: {"model": ErrorResponse, "description": "Unauthorized"},
        409: {"model": ErrorResponse, "description": "Tenant already exists"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
    summary="Create a new tenant",
    description="""
Create a new tenant with default configuration.

**Authentication**: Requires valid JWT token.
**Authorization**: Requires `PlatformAdmin` role or `tenants:admin` permission.

**Idempotency**: Include `Idempotency-Key` header for safe retries.
If the same key is reused with the same request payload, the original
response is returned. If reused with a different payload, returns 409 Conflict.
""",
)
async def create_tenant(
    request: CreateTenantRequest,
    principal: Annotated[Any, Depends(require_platform_admin)],
    service: Annotated[TenantProvisioningService, Depends(get_provisioning_service)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    """Create a new tenant with provisioning."""
    created_by = getattr(principal, "subject", "unknown")

    try:
        response, status_code, was_idempotent = await service.create_tenant(
            request=request,
            created_by=created_by,
            idempotency_key=idempotency_key,
        )

        headers = {}
        if was_idempotent:
            headers["X-Idempotent-Replay"] = "true"

        return JSONResponse(
            status_code=status_code,
            content=response.model_dump(mode="json"),
            headers=headers,
        )

    except TenantExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "conflict", "message": str(e)},
        )
    except IdempotencyConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "idempotency_conflict", "message": str(e)},
        )


@router.get(
    "/{tenant_id}",
    response_model=TenantResponse,
    responses={
        200: {"description": "Tenant found"},
        401: {"model": ErrorResponse, "description": "Unauthenticated"},
        403: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Tenant not found"},
    },
    summary="Get tenant by ID",
    description="Retrieve tenant details. Requires `tenants:read` permission.",
)
async def get_tenant(
    tenant_id: UUID,
    principal: Annotated[Any, Depends(get_principal)],
    service: Annotated[TenantProvisioningService, Depends(get_provisioning_service)],
) -> TenantResponse:
    """Get tenant by ID."""
    # Check read permission
    effective_permissions = getattr(principal, "effective_permissions", frozenset())
    if not (
        "*" in effective_permissions
        or "tenants:read" in effective_permissions
        or "tenants:admin" in effective_permissions
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "message": "tenants:read permission required"},
        )

    tenant = await service.get_tenant(tenant_id)
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Tenant not found"},
        )
    return tenant


@router.get(
    "/{tenant_id}/configurations",
    response_model=list[TenantConfigurationResponse],
    responses={
        200: {"description": "Configurations retrieved"},
        401: {"model": ErrorResponse, "description": "Unauthenticated"},
        403: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Tenant not found"},
    },
    summary="Get tenant configurations",
    description="Retrieve tenant configuration entries. Requires `tenants:read` permission.",
)
async def get_tenant_configurations(
    tenant_id: UUID,
    principal: Annotated[Any, Depends(get_principal)],
    service: Annotated[TenantProvisioningService, Depends(get_provisioning_service)],
    category: ConfigCategory | None = None,
) -> list[TenantConfigurationResponse]:
    """Get configurations for a tenant."""
    effective_permissions = getattr(principal, "effective_permissions", frozenset())
    if not (
        "*" in effective_permissions
        or "tenants:read" in effective_permissions
        or "tenants:admin" in effective_permissions
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "message": "tenants:read permission required"},
        )

    # Verify tenant exists
    tenant = await service.get_tenant(tenant_id)
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Tenant not found"},
        )

    return await service.get_tenant_configurations(tenant_id, category)
