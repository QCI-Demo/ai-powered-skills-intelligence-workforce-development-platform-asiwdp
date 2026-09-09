"""FastAPI dependencies for tenant provisioning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status

from asiwdp_tenant_provisioning.controllers.provisioning_controller import (
    ProvisioningController,
)
from asiwdp_tenant_provisioning.events.publisher import (
    InMemoryEventBus,
    TenantProvisioningPublisher,
)
from asiwdp_tenant_provisioning.rbac import PLATFORM_ADMIN_ROLES, is_platform_admin
from asiwdp_tenant_provisioning.store import InMemoryTenantStore


@dataclass(frozen=True, slots=True)
class ActorContext:
    subject: str
    tenant_id: str | None
    roles: tuple[str, ...]
    principal: object


def get_store(request: Request) -> InMemoryTenantStore:
    store = getattr(request.app.state, "tenant_store", None)
    if store is None:
        raise RuntimeError("Tenant store is not configured")
    return store


def get_event_bus(request: Request) -> InMemoryEventBus:
    bus = getattr(request.app.state, "event_bus", None)
    if bus is None:
        raise RuntimeError("Event bus is not configured")
    return bus


def get_publisher(
    bus: Annotated[InMemoryEventBus, Depends(get_event_bus)],
) -> TenantProvisioningPublisher:
    return TenantProvisioningPublisher(bus)


def get_controller(
    store: Annotated[InMemoryTenantStore, Depends(get_store)],
    publisher: Annotated[TenantProvisioningPublisher, Depends(get_publisher)],
) -> ProvisioningController:
    return ProvisioningController(store, publisher)


def _principal_from_request(request: Request) -> object | None:
    """Resolve principal attached by Story S2 AuthMiddleware."""
    state = request.state
    principal = getattr(state, "principal", None)
    if principal is None and isinstance(state, dict):
        principal = state.get("principal")
    return principal


def require_platform_admin(request: Request) -> ActorContext:
    """
    Enforce Story S2 auth + PlatformAdmin RBAC on provisioning.

    * 401 — missing/unauthenticated principal (Bearer JWT required)
    * 403 — authenticated caller without PlatformAdmin / platform_admin
    """
    principal = _principal_from_request(request)
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "unauthenticated",
                "message": "Bearer access token required",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not is_platform_admin(principal):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "forbidden",
                "message": (
                    "PlatformAdmin role required to provision tenants; "
                    f"accepted roles: {', '.join(sorted(PLATFORM_ADMIN_ROLES))}"
                ),
            },
        )
    roles = tuple(getattr(principal, "roles", ()) or ())
    return ActorContext(
        subject=str(getattr(principal, "subject", "")),
        tenant_id=getattr(principal, "tenant_id", None),
        roles=roles,
        principal=principal,
    )


def require_idempotency_key(
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> str:
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "idempotency_key_required",
                "message": "Idempotency-Key header is required",
            },
        )
    key = idempotency_key.strip()
    if len(key) < 8 or len(key) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_idempotency_key",
                "message": "Idempotency-Key must be 8-128 characters",
            },
        )
    return key


def actor_uuid(actor: ActorContext) -> UUID | None:
    try:
        return UUID(actor.subject)
    except (ValueError, TypeError):
        return None
