"""Tenant provisioning controller with idempotency and RBAC."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import ValidationError

from src.events.publisher import (
    EventPublisher,
    get_event_publisher,
)
from src.schemas.defaults import (
    get_default_configurations_for_tier,
)
from src.schemas.tenant import (
    CreateTenantRequest,
    ErrorResponse,
    TenantProvisioningResponse,
    TenantResponse,
    TenantStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tenants", tags=["Tenants"])

# Idempotency key TTL (24 hours)
IDEMPOTENCY_KEY_TTL = timedelta(hours=24)


class TenantRepository:
    """Repository for tenant persistence operations.

    This is an abstract interface. Concrete implementations should use
    PostgreSQL or MongoDB depending on deployment configuration.
    """

    async def get_by_id(self, tenant_id: UUID) -> dict[str, Any] | None:
        raise NotImplementedError

    async def get_by_slug(self, slug: str) -> dict[str, Any] | None:
        raise NotImplementedError

    async def get_by_name(self, name: str) -> dict[str, Any] | None:
        raise NotImplementedError

    async def create(self, tenant_data: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    async def create_configurations(
        self, tenant_id: UUID, configs: dict[str, Any]
    ) -> int:
        raise NotImplementedError


class IdempotencyStore:
    """Store for idempotency key tracking."""

    async def get(self, key: str) -> dict[str, Any] | None:
        raise NotImplementedError

    async def set(
        self,
        key: str,
        tenant_id: UUID | None,
        request_hash: str,
        response: dict[str, Any],
        expires_at: datetime,
    ) -> None:
        raise NotImplementedError


class InMemoryTenantRepository(TenantRepository):
    """In-memory implementation for testing."""

    def __init__(self) -> None:
        self._tenants: dict[UUID, dict[str, Any]] = {}
        self._configurations: dict[UUID, dict[str, Any]] = {}

    async def get_by_id(self, tenant_id: UUID) -> dict[str, Any] | None:
        return self._tenants.get(tenant_id)

    async def get_by_slug(self, slug: str) -> dict[str, Any] | None:
        for tenant in self._tenants.values():
            if tenant.get("slug") == slug:
                return tenant
        return None

    async def get_by_name(self, name: str) -> dict[str, Any] | None:
        for tenant in self._tenants.values():
            if tenant.get("name") == name:
                return tenant
        return None

    async def create(self, tenant_data: dict[str, Any]) -> dict[str, Any]:
        tenant_id = tenant_data["tenant_id"]
        self._tenants[tenant_id] = tenant_data
        return tenant_data

    async def create_configurations(
        self, tenant_id: UUID, configs: dict[str, Any]
    ) -> int:
        self._configurations[tenant_id] = configs
        return len(configs)


class InMemoryIdempotencyStore(IdempotencyStore):
    """In-memory idempotency store for testing."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    async def get(self, key: str) -> dict[str, Any] | None:
        entry = self._store.get(key)
        if entry and entry.get("expires_at", datetime.min) > datetime.now(timezone.utc):
            return entry
        return None

    async def set(
        self,
        key: str,
        tenant_id: UUID | None,
        request_hash: str,
        response: dict[str, Any],
        expires_at: datetime,
    ) -> None:
        self._store[key] = {
            "tenant_id": tenant_id,
            "request_hash": request_hash,
            "response": response,
            "created_at": datetime.now(timezone.utc),
            "expires_at": expires_at,
        }


# Global instances (replaced at app startup with real implementations)
_tenant_repo: TenantRepository | None = None
_idempotency_store: IdempotencyStore | None = None


def get_tenant_repository() -> TenantRepository:
    global _tenant_repo
    if _tenant_repo is None:
        _tenant_repo = InMemoryTenantRepository()
    return _tenant_repo


def set_tenant_repository(repo: TenantRepository) -> None:
    global _tenant_repo
    _tenant_repo = repo


def get_idempotency_store() -> IdempotencyStore:
    global _idempotency_store
    if _idempotency_store is None:
        _idempotency_store = InMemoryIdempotencyStore()
    return _idempotency_store


def set_idempotency_store(store: IdempotencyStore) -> None:
    global _idempotency_store
    _idempotency_store = store


def _compute_request_hash(body: bytes) -> str:
    """Compute SHA-256 hash of request body for idempotency comparison."""
    return hashlib.sha256(body).hexdigest()


def _require_platform_admin(request: Request) -> None:
    """Check that the authenticated principal has platform_admin role.

    Integrates with asiwdp-auth middleware from Story S2.

    Raises:
        HTTPException: 401 if unauthenticated, 403 if unauthorized.
    """
    principal = getattr(request.state, "principal", None)
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthenticated", "message": "Authentication required"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check for platform_admin role or wildcard permission
    has_admin_role = "platform_admin" in getattr(principal, "roles", ())
    has_wildcard = "*" in getattr(principal, "effective_permissions", frozenset())
    has_tenants_admin = "tenants:admin" in getattr(
        principal, "effective_permissions", frozenset()
    )

    if not (has_admin_role or has_wildcard or has_tenants_admin):
        logger.warning(
            "Authorization denied for tenant creation: subject=%s roles=%s",
            getattr(principal, "subject", "unknown"),
            getattr(principal, "roles", []),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "forbidden",
                "message": "PlatformAdmin role required for tenant provisioning",
            },
        )


@router.post(
    "",
    response_model=TenantProvisioningResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {
            "model": TenantProvisioningResponse,
            "description": "Idempotent response (tenant already exists)",
        },
        400: {"model": ErrorResponse, "description": "Validation error"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        409: {"model": ErrorResponse, "description": "Tenant already exists"},
        422: {"model": ErrorResponse, "description": "Request body validation failed"},
    },
    summary="Provision a new tenant",
    description="""
Create a new tenant with default configuration. Requires PlatformAdmin role.

**Idempotency**: Provide an `Idempotency-Key` header to enable idempotent 
behavior. If the same key is used with an identical request body within 24 hours,
the original response is returned without creating a duplicate tenant.

**Events**: On successful provisioning, a `tenant.provisioning.completed` event
is emitted to the centralized event bus for downstream services.
""",
)
async def create_tenant(
    request: Request,
    body: CreateTenantRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    tenant_repo: TenantRepository = Depends(get_tenant_repository),
    idempotency_store: IdempotencyStore = Depends(get_idempotency_store),
    event_publisher: EventPublisher = Depends(get_event_publisher),
) -> TenantProvisioningResponse:
    """Create a new tenant with idempotency support."""
    # RBAC check: require PlatformAdmin
    _require_platform_admin(request)

    # Get requesting user info from principal
    principal = request.state.principal
    provisioned_by = UUID(principal.subject) if principal.subject else None
    correlation_id = request.headers.get("X-Correlation-ID")

    # Compute request hash for idempotency
    raw_body = await request.body()
    request_hash = _compute_request_hash(raw_body)

    # Check idempotency key if provided
    if idempotency_key:
        existing = await idempotency_store.get(idempotency_key)
        if existing:
            # Verify request body matches
            if existing.get("request_hash") == request_hash:
                logger.info(
                    "Returning idempotent response for key=%s tenant=%s",
                    idempotency_key,
                    existing.get("tenant_id"),
                )
                cached_response = existing.get("response", {})
                return TenantProvisioningResponse(
                    tenant=TenantResponse(**cached_response.get("tenant", {})),
                    idempotent=True,
                    message="Tenant already provisioned (idempotent response)",
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": "idempotency_mismatch",
                        "message": "Idempotency key already used with different request body",
                    },
                )

    # Check for existing tenant by name or slug
    existing_by_name = await tenant_repo.get_by_name(body.name)
    if existing_by_name:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "tenant_exists",
                "message": f"Tenant with name '{body.name}' already exists",
            },
        )

    existing_by_slug = await tenant_repo.get_by_slug(body.slug)
    if existing_by_slug:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "tenant_exists",
                "message": f"Tenant with slug '{body.slug}' already exists",
            },
        )

    # Create tenant
    now = datetime.now(timezone.utc)
    tenant_id = uuid4()

    tenant_data = {
        "tenant_id": tenant_id,
        "name": body.name,
        "slug": body.slug,
        "display_name": body.display_name,
        "status": TenantStatus.PROVISIONING.value,
        "tier": body.tier.value,
        "owner_user_id": body.owner_user_id,
        "contact_email": body.contact_email,
        "metadata": body.metadata,
        "created_at": now,
        "updated_at": now,
        "provisioned_at": None,
        "provisioned_by": provisioned_by,
    }

    # Emit provisioning started event
    await event_publisher.publish_provisioning_started(
        tenant_id,
        name=body.name,
        tier=body.tier.value,
        provisioned_by=provisioned_by,
        correlation_id=correlation_id,
    )

    try:
        # Persist tenant atomically with default configuration
        created_tenant = await tenant_repo.create(tenant_data)

        # Initialize default configurations based on tier
        default_configs = get_default_configurations_for_tier(body.tier.value)
        config_count = await tenant_repo.create_configurations(tenant_id, default_configs)

        # Update tenant status to active
        created_tenant["status"] = TenantStatus.ACTIVE.value
        created_tenant["provisioned_at"] = datetime.now(timezone.utc)

        # Emit provisioning completed event
        await event_publisher.publish_provisioning_completed(
            tenant_id,
            name=body.name,
            slug=body.slug,
            tier=body.tier.value,
            config_count=config_count,
            provisioned_by=provisioned_by,
            correlation_id=correlation_id,
        )

        tenant_response = TenantResponse(
            tenant_id=created_tenant["tenant_id"],
            name=created_tenant["name"],
            slug=created_tenant["slug"],
            display_name=created_tenant.get("display_name"),
            status=TenantStatus(created_tenant["status"]),
            tier=body.tier,
            owner_user_id=created_tenant.get("owner_user_id"),
            contact_email=created_tenant["contact_email"],
            metadata=created_tenant.get("metadata", {}),
            created_at=created_tenant["created_at"],
            updated_at=created_tenant["updated_at"],
            provisioned_at=created_tenant.get("provisioned_at"),
            provisioned_by=created_tenant.get("provisioned_by"),
        )

        response = TenantProvisioningResponse(
            tenant=tenant_response,
            idempotent=False,
            message="Tenant provisioned successfully",
        )

        # Store in idempotency cache if key provided
        if idempotency_key:
            expires_at = datetime.now(timezone.utc) + IDEMPOTENCY_KEY_TTL
            await idempotency_store.set(
                idempotency_key,
                tenant_id,
                request_hash,
                response.model_dump(mode="json"),
                expires_at,
            )

        logger.info(
            "Tenant provisioned: id=%s name=%s slug=%s tier=%s",
            tenant_id,
            body.name,
            body.slug,
            body.tier.value,
        )

        return response

    except Exception as exc:
        # Emit provisioning failed event
        await event_publisher.publish_provisioning_failed(
            tenant_id,
            error=str(exc),
            error_code="provisioning_error",
            correlation_id=correlation_id,
        )
        logger.error("Tenant provisioning failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "provisioning_failed",
                "message": "Failed to provision tenant",
            },
        ) from exc


@router.get(
    "/{tenant_id}",
    response_model=TenantResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Tenant not found"},
    },
    summary="Get tenant by ID",
    description="Retrieve tenant details. Requires tenants:read permission.",
)
async def get_tenant(
    tenant_id: UUID,
    request: Request,
    tenant_repo: TenantRepository = Depends(get_tenant_repository),
) -> TenantResponse:
    """Get a tenant by ID."""
    # Check authentication
    principal = getattr(request.state, "principal", None)
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthenticated", "message": "Authentication required"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check permission
    has_permission = (
        "*" in getattr(principal, "effective_permissions", frozenset())
        or "tenants:read" in getattr(principal, "effective_permissions", frozenset())
    )
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "message": "tenants:read permission required"},
        )

    tenant = await tenant_repo.get_by_id(tenant_id)
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Tenant not found"},
        )

    return TenantResponse(**tenant)
