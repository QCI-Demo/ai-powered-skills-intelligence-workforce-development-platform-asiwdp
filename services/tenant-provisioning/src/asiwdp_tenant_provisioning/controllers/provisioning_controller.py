"""Provisioning controller: validation, idempotency, persistence, events."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from asiwdp_tenant_provisioning.events.publisher import TenantProvisioningPublisher
from asiwdp_tenant_provisioning.models import ProvisionedTenant
from asiwdp_tenant_provisioning.schemas.requests import TenantProvisionRequest
from asiwdp_tenant_provisioning.store import (
    ConflictError,
    IdempotencyConflictError,
    InMemoryTenantStore,
)


class ProvisioningController:
    def __init__(
        self,
        store: InMemoryTenantStore,
        publisher: TenantProvisioningPublisher,
    ) -> None:
        self._store = store
        self._publisher = publisher

    def provision(
        self,
        request: TenantProvisionRequest,
        *,
        idempotency_key: str,
        actor_id: UUID | None,
        requesting_tenant_id: str | None,
    ) -> tuple[ProvisionedTenant, dict[str, Any] | None]:
        """
        Create or replay a tenant provisioning request.

        Returns (provisioned, event_or_none). Event is only emitted on first create.
        """
        payload = request.model_dump(by_alias=True, exclude_none=False)
        request_hash = self._store.hash_request(payload)

        cfg = request.configuration
        overrides: dict[str, Any] = {}
        if cfg is not None:
            if cfg.locale is not None:
                overrides["locale"] = cfg.locale
            if cfg.timezone is not None:
                overrides["timezone"] = cfg.timezone
            if cfg.features is not None:
                overrides["features"] = cfg.features
            if cfg.privacy is not None:
                overrides["privacy"] = cfg.privacy
            if cfg.metering_enabled is not None:
                overrides["metering_enabled"] = cfg.metering_enabled
            if cfg.gdpr_enabled is not None:
                overrides["gdpr_enabled"] = cfg.gdpr_enabled
            if cfg.ccpa_enabled is not None:
                overrides["ccpa_enabled"] = cfg.ccpa_enabled

        try:
            result = self._store.provision(
                slug=request.slug,
                display_name=request.display_name,
                plan_code=request.plan_code,
                data_residency=request.data_residency,
                created_by=actor_id,
                configuration_overrides=overrides or None,
                metadata=request.metadata,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
        except ConflictError:
            raise
        except IdempotencyConflictError:
            raise

        event: dict[str, Any] | None = None
        if result.created:
            event = self._publisher.publish_provisioned(
                result,
                requesting_tenant_id=requesting_tenant_id,
                idempotency_key=idempotency_key,
            )
        return result, event
