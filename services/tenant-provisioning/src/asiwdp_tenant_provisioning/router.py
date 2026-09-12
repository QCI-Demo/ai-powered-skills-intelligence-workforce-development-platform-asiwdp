"""API routes for tenant provisioning."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response, status

from asiwdp_tenant_provisioning.controllers.provisioning_controller import (
    ProvisioningController,
)
from asiwdp_tenant_provisioning.deps import (
    ActorContext,
    actor_uuid,
    get_controller,
    require_idempotency_key,
    require_platform_admin,
)
from asiwdp_tenant_provisioning.schemas.requests import TenantProvisionRequest
from asiwdp_tenant_provisioning.store import ConflictError, IdempotencyConflictError

api_router = APIRouter()


@api_router.get("/tenants/health", tags=["Health"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "tenant-provisioning"}


@api_router.post(
    "/tenants",
    status_code=status.HTTP_201_CREATED,
    tags=["Tenants"],
    summary="Provision a new tenant (idempotent)",
)
def create_tenant(
    body: TenantProvisionRequest,
    response: Response,
    actor: Annotated[ActorContext, Depends(require_platform_admin)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
    controller: Annotated[ProvisioningController, Depends(get_controller)],
) -> dict[str, Any]:
    """
    Create a tenant, seed default configuration, store metadata, and emit
    a tenant-scoped provisioning event. Replays with the same Idempotency-Key
    return the original tenant with HTTP 200 and ``created=false``.
    """
    try:
        result, _event = controller.provision(
            body,
            idempotency_key=idempotency_key,
            actor_id=actor_uuid(actor),
            requesting_tenant_id=actor.tenant_id,
        )
    except ConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "conflict", "message": str(exc)},
        ) from exc
    except IdempotencyConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "idempotency_conflict", "message": str(exc)},
        ) from exc

    payload = result.to_response_dict()
    response.status_code = (
        status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
    )
    return payload
