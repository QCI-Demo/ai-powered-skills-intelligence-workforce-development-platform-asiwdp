"""Tenant provisioning service with RBAC and idempotency.

Task: 78cab998-3bb5-4262-bc80-e2160bdc2805 - Implement POST /api/tenants endpoint
Task: ca4babed-4042-4c03-97bc-9705218cbfc9 - Integrate authentication middleware and RBAC checks
Task: 4a9fb493-572e-4e33-bac6-eeb81ba43ec1 - Publish tenant provisioning event
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse

from tenant_provisioning.database import TenantRepository
from tenant_provisioning.events import EventPublisher, create_tenant_provisioned_event
from tenant_provisioning.models import CreateTenantRequest, ErrorResponse

logger = logging.getLogger(__name__)

# Required role for tenant provisioning
# Task: ca4babed-4042-4c03-97bc-9705218cbfc9
PLATFORM_ADMIN_ROLE = "platform_admin"


def _get_principal(request: Request) -> Any:
    """Extract principal from request state."""
    state = request.state
    principal = getattr(state, "principal", None)
    if principal is None and isinstance(state, dict):
        principal = state.get("principal")
    return principal


def _error_response(status_code: int, error: str, message: str, details: dict[str, Any] | None = None) -> JSONResponse:
    """Create a standardized error response."""
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(error=error, message=message, details=details).model_dump(),
    )


class TenantProvisioningService:
    """Service for tenant provisioning operations.
    
    Task: 78cab998-3bb5-4262-bc80-e2160bdc2805
    """

    def __init__(
        self,
        repository: TenantRepository,
        event_publisher: EventPublisher,
        idempotency_ttl_hours: int = 24,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher
        self._idempotency_ttl_hours = idempotency_ttl_hours

    async def create_tenant(self, request: Request) -> JSONResponse:
        """Handle POST /api/tenants endpoint.
        
        Task: 78cab998-3bb5-4262-bc80-e2160bdc2805
        - Validate payload against schema
        - Check Idempotency-Key store; create or return existing tenant
        - Persist tenant and default configuration atomically
        
        Task: ca4babed-4042-4c03-97bc-9705218cbfc9
        - Apply middleware from Story S2
        - Add role check for "PlatformAdmin"
        - Return 403 for unauthorized attempts
        
        Task: 4a9fb493-572e-4e33-bac6-eeb81ba43ec1
        - Publish event after successful tenant creation
        """
        # Get authenticated principal
        principal = _get_principal(request)
        if principal is None:
            return _error_response(
                401,
                "unauthenticated",
                "Authentication required",
            )

        # RBAC check: only platform_admin can create tenants
        # Task: ca4babed-4042-4c03-97bc-9705218cbfc9
        if not self._has_platform_admin_role(principal):
            logger.warning(
                "Unauthorized tenant creation attempt by %s with roles %s",
                principal.subject,
                principal.roles,
            )
            return _error_response(
                403,
                "forbidden",
                "Only platform administrators can create tenants",
            )

        # Parse and validate request body
        # Task: 78cab998-3bb5-4262-bc80-e2160bdc2805
        try:
            body = await request.json()
            create_request = CreateTenantRequest.model_validate(body)
        except ValidationError as e:
            return _error_response(
                400,
                "validation_error",
                "Invalid request body",
                details={"errors": e.errors()},
            )
        except Exception:
            return _error_response(
                400,
                "invalid_json",
                "Request body must be valid JSON",
            )

        # Check idempotency key
        # Task: 78cab998-3bb5-4262-bc80-e2160bdc2805
        idempotency_key = request.headers.get("Idempotency-Key")
        if idempotency_key:
            try:
                exists, cached_response = await self._repository.check_idempotency_key(
                    idempotency_key,
                    create_request,
                )
                if exists and cached_response:
                    logger.info(
                        "Returning cached response for idempotency key %s",
                        idempotency_key,
                    )
                    return JSONResponse(status_code=200, content=cached_response)
            except ValueError as e:
                return _error_response(
                    409,
                    "idempotency_conflict",
                    str(e),
                )

        # Create tenant with configuration atomically
        # Task: 78cab998-3bb5-4262-bc80-e2160bdc2805
        try:
            tenant = await self._repository.create_tenant(
                create_request,
                created_by=principal.subject,
                idempotency_key=idempotency_key,
                idempotency_ttl_hours=self._idempotency_ttl_hours,
            )
        except ValueError as e:
            error_msg = str(e)
            if "already exists" in error_msg:
                return _error_response(
                    409,
                    "conflict",
                    error_msg,
                )
            return _error_response(
                400,
                "invalid_request",
                error_msg,
            )
        except Exception as e:
            logger.exception("Failed to create tenant")
            return _error_response(
                500,
                "internal_error",
                "Failed to create tenant",
            )

        # Publish provisioning event
        # Task: 4a9fb493-572e-4e33-bac6-eeb81ba43ec1
        try:
            event = create_tenant_provisioned_event(tenant)
            await self._event_publisher.publish(event)
            logger.info(
                "Published tenant.provisioned event for tenant %s",
                tenant.id,
            )
        except Exception as e:
            logger.error(
                "Failed to publish event for tenant %s: %s",
                tenant.id,
                str(e),
            )
            # Don't fail the request if event publishing fails
            # The tenant is already created successfully

        return JSONResponse(
            status_code=201,
            content=tenant.model_dump(by_alias=True, mode="json"),
        )

    def _has_platform_admin_role(self, principal: Any) -> bool:
        """Check if principal has platform_admin role.
        
        Task: ca4babed-4042-4c03-97bc-9705218cbfc9
        """
        # Check for wildcard permission (platform_admin has "*")
        if hasattr(principal, "effective_permissions"):
            if "*" in principal.effective_permissions:
                return True

        # Check for explicit role
        if hasattr(principal, "roles"):
            if PLATFORM_ADMIN_ROLE in principal.roles:
                return True

        # Check has_role method if available
        if hasattr(principal, "has_role"):
            return principal.has_role(PLATFORM_ADMIN_ROLE)

        return False
