"""Tenant provisioning application service."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from asiwdp_auth.context import Principal

from asiwdp_tenant_provisioning.defaults import (
    build_default_configuration,
    default_config_keys,
)
from asiwdp_tenant_provisioning.events import (
    EventBus,
    build_tenant_provisioned_event,
)
from asiwdp_tenant_provisioning.models import (
    ConfigurationRecord,
    MetadataRecord,
    ProvisionResult,
    TenantRecord,
)
from asiwdp_tenant_provisioning.repository import ConflictError, TenantRepository
from asiwdp_tenant_provisioning.schemas import (
    ConfigurationItem,
    MetadataItem,
    TenantCreateRequest,
    TenantResponse,
)


def _request_hash(payload: TenantCreateRequest) -> str:
    canonical = json.dumps(
        payload.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _serialize_response(
    tenant: TenantRecord,
    configs: list[ConfigurationRecord],
    metas: list[MetadataRecord],
    idempotent_replay: bool,
) -> dict[str, Any]:
    response = TenantResponse(
        tenant_id=tenant.tenant_id,
        slug=tenant.slug,
        display_name=tenant.display_name,
        status=tenant.status,
        plan_code=tenant.plan_code,
        region=tenant.region,
        timezone=tenant.timezone,
        contact=tenant.contact,
        provisioned_at=tenant.provisioned_at,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
        created_by=tenant.created_by,
        configuration=[
            ConfigurationItem(
                config_key=c.config_key,
                config_value=c.config_value,
                is_default=c.is_default,
                version=c.version,
            )
            for c in configs
        ],
        metadata=[
            MetadataItem(meta_key=m.meta_key, meta_value=m.meta_value) for m in metas
        ],
        idempotent_replay=idempotent_replay,
    )
    return response.model_dump(mode="json")


class TenantProvisioningService:
    def __init__(self, repository: TenantRepository, event_bus: EventBus) -> None:
        self._repo = repository
        self._events = event_bus

    def provision(
        self,
        payload: TenantCreateRequest,
        *,
        principal: Principal,
        idempotency_key: str | None = None,
        correlation_id: str | None = None,
    ) -> tuple[TenantResponse, int]:
        """Create tenant or return prior result for the same Idempotency-Key.

        Returns (response_model, http_status).
        """
        req_hash = _request_hash(payload)
        defaults = build_default_configuration(
            timezone=payload.timezone,
            region=payload.region,
        )

        def response_builder(
            tenant: TenantRecord,
            configs: list[ConfigurationRecord],
            metas: list[MetadataRecord],
            replay: bool,
        ) -> dict[str, Any]:
            return _serialize_response(tenant, configs, metas, replay)

        try:
            tenant, configs, metas, created = self._repo.create_tenant_atomic(
                slug=payload.slug,
                display_name=payload.display_name,
                plan_code=payload.plan_code,
                region=payload.region,
                timezone_name=payload.timezone,
                contact=payload.contact,
                created_by=principal.subject,
                default_config=defaults,
                metadata=payload.metadata,
                idempotency_key=idempotency_key,
                requesting_tenant_id=(
                    UUID(principal.tenant_id) if principal.tenant_id else None
                ),
                request_hash=req_hash,
                response_builder=response_builder,
            )
        except ConflictError as exc:
            raise ConflictError(exc.message) from exc

        if created:
            event = build_tenant_provisioned_event(
                tenant_id=tenant.tenant_id,
                slug=tenant.slug,
                display_name=tenant.display_name,
                status=tenant.status,
                plan_code=tenant.plan_code,
                region=tenant.region,
                timezone_name=tenant.timezone,
                default_config_keys=default_config_keys(
                    timezone=tenant.timezone, region=tenant.region
                ),
                actor_subject=principal.subject,
                actor_roles=principal.roles,
                requesting_tenant_id=principal.tenant_id,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            )
            self._events.publish(event)
            body = TenantResponse.model_validate(
                _serialize_response(tenant, configs, metas, False)
            )
            return body, 201

        body = TenantResponse.model_validate(
            _serialize_response(tenant, configs, metas, True)
        )
        return body, 200


__all__ = ["TenantProvisioningService", "ConflictError", "_serialize_response"]
