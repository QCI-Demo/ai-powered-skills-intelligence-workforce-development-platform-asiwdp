"""Tenant provisioning service with business logic."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tenant_provisioning.default_config import get_default_configurations
from tenant_provisioning.entities import (
    ProvisioningEvent,
    Tenant,
    TenantAuditLog,
    TenantConfiguration,
    TenantMetadata,
)
from tenant_provisioning.events import EventPublisher
from tenant_provisioning.idempotency import IdempotencyConflictError, IdempotencyService
from tenant_provisioning.models import (
    ConfigCategory,
    CreateTenantRequest,
    CreateTenantResponse,
    EventStatus,
    TenantConfigurationResponse,
    TenantResponse,
    TenantStatus,
)


class TenantProvisioningService:
    """Service for provisioning new tenants with default configuration."""

    def __init__(
        self,
        session: AsyncSession,
        idempotency_service: IdempotencyService | None = None,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        self._session = session
        self._idempotency = idempotency_service or IdempotencyService(session)
        self._events = event_publisher or EventPublisher(session)

    async def create_tenant(
        self,
        request: CreateTenantRequest,
        created_by: str,
        idempotency_key: str | None = None,
    ) -> tuple[CreateTenantResponse, int, bool]:
        """Create a new tenant with default configuration.

        Args:
            request: Tenant creation request
            created_by: User ID creating the tenant
            idempotency_key: Optional idempotency key for safe retries

        Returns:
            Tuple of (response, status_code, was_idempotent)

        Raises:
            TenantExistsError: If tenant with same name or domain exists
            IdempotencyConflictError: If idempotency key reused with different payload
        """
        request_dict = request.model_dump()

        # Check idempotency
        if idempotency_key:
            request_hash = self._idempotency.compute_request_hash(request_dict)
            cached = await self._idempotency.get_cached_response(
                idempotency_key, request_hash
            )
            if cached:
                response_body, status_code = cached
                return (
                    CreateTenantResponse.model_validate(response_body),
                    status_code,
                    True,
                )

        # Check for existing tenant
        existing = await self._get_tenant_by_name(request.name)
        if existing:
            raise TenantExistsError(f"Tenant with name '{request.name}' already exists")

        if request.domain:
            existing_domain = await self._get_tenant_by_domain(request.domain)
            if existing_domain:
                raise TenantExistsError(
                    f"Tenant with domain '{request.domain}' already exists"
                )

        # Create tenant atomically
        tenant = Tenant(
            name=request.name,
            display_name=request.display_name or request.name,
            domain=request.domain,
            status=TenantStatus.PENDING,
            plan_tier=request.plan_tier,
            settings=request.settings,
            created_by=created_by,
        )
        self._session.add(tenant)
        await self._session.flush()

        # Create default configurations
        default_configs = get_default_configurations(request.plan_tier)
        configurations: list[TenantConfiguration] = []
        for cfg in default_configs:
            config = TenantConfiguration(
                tenant_id=tenant.tenant_id,
                config_key=cfg["config_key"],
                config_value=cfg["config_value"],
                category=cfg["category"],
            )
            self._session.add(config)
            configurations.append(config)

        await self._session.flush()

        # Create metadata entries
        for key, value in request.metadata.items():
            metadata = TenantMetadata(
                tenant_id=tenant.tenant_id,
                metadata_key=key,
                metadata_value=str(value),
            )
            self._session.add(metadata)

        # Mark as active
        tenant.status = TenantStatus.ACTIVE
        tenant.provisioned_at = datetime.now(timezone.utc)
        await self._session.flush()

        # Create audit log
        audit = TenantAuditLog(
            tenant_id=tenant.tenant_id,
            action="tenant.created",
            actor_id=created_by,
            actor_type="user",
            resource_type="tenant",
            resource_id=str(tenant.tenant_id),
            changes={"created": request_dict},
        )
        self._session.add(audit)
        await self._session.flush()

        # Publish provisioning event
        await self._events.publish_tenant_provisioned(
            tenant_id=tenant.tenant_id,
            tenant_name=tenant.name,
            plan_tier=tenant.plan_tier,
            created_by=created_by,
            metadata={"domain": tenant.domain, **request.metadata},
        )

        # Build response
        tenant_response = TenantResponse(
            tenant_id=tenant.tenant_id,
            name=tenant.name,
            display_name=tenant.display_name,
            domain=tenant.domain,
            status=tenant.status,
            plan_tier=tenant.plan_tier,
            settings=tenant.settings,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at,
            created_by=tenant.created_by,
            provisioned_at=tenant.provisioned_at,
        )

        config_responses = [
            TenantConfigurationResponse(
                config_id=c.config_id,
                config_key=c.config_key,
                config_value=c.config_value,
                category=c.category,
                is_active=c.is_active,
                version=c.version,
            )
            for c in configurations
        ]

        response = CreateTenantResponse(
            tenant=tenant_response,
            configurations=config_responses,
            idempotent=False,
        )

        # Store for idempotency
        if idempotency_key:
            request_hash = self._idempotency.compute_request_hash(request_dict)
            await self._idempotency.store_response(
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                response_body=response.model_dump(mode="json"),
                status_code=201,
                tenant_id=tenant.tenant_id,
            )

        return response, 201, False

    async def get_tenant(self, tenant_id: UUID) -> TenantResponse | None:
        """Get tenant by ID."""
        stmt = select(Tenant).where(Tenant.tenant_id == tenant_id)
        result = await self._session.execute(stmt)
        tenant = result.scalar_one_or_none()
        if tenant is None:
            return None
        return TenantResponse.model_validate(tenant)

    async def _get_tenant_by_name(self, name: str) -> Tenant | None:
        """Get tenant by name."""
        stmt = select(Tenant).where(Tenant.name == name.lower())
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_tenant_by_domain(self, domain: str) -> Tenant | None:
        """Get tenant by domain."""
        stmt = select(Tenant).where(Tenant.domain == domain.lower())
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_tenant_configurations(
        self,
        tenant_id: UUID,
        category: ConfigCategory | None = None,
    ) -> list[TenantConfigurationResponse]:
        """Get configurations for a tenant."""
        stmt = select(TenantConfiguration).where(
            TenantConfiguration.tenant_id == tenant_id,
            TenantConfiguration.is_active == True,
        )
        if category:
            stmt = stmt.where(TenantConfiguration.category == category)

        result = await self._session.execute(stmt)
        configs = result.scalars().all()
        return [TenantConfigurationResponse.model_validate(c) for c in configs]

    async def get_provisioning_events(
        self,
        tenant_id: UUID,
        status: EventStatus | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get provisioning events for a tenant."""
        stmt = select(ProvisioningEvent).where(
            ProvisioningEvent.tenant_id == tenant_id
        )
        if status:
            stmt = stmt.where(ProvisioningEvent.status == status)
        stmt = stmt.order_by(ProvisioningEvent.created_at.desc()).limit(limit)

        result = await self._session.execute(stmt)
        events = result.scalars().all()
        return [e.event_payload for e in events]


class TenantExistsError(Exception):
    """Raised when attempting to create a tenant that already exists."""

    pass
