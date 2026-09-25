"""Tenant provisioning service with idempotency and event publishing."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from tenant_provisioning.database import (
    IdempotencyKey,
    Tenant,
    TenantAuditLog,
    TenantConfiguration as TenantConfigDB,
)
from tenant_provisioning.events import EventPublisher, EventTypes, TenantProvisioningEvent
from tenant_provisioning.models import (
    CreateTenantRequest,
    TenantConfiguration,
    TenantResponse,
    TenantStatus,
    TenantTier,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class TenantExistsError(Exception):
    """Raised when attempting to create a tenant with an existing slug."""

    def __init__(self, slug: str) -> None:
        super().__init__(f"Tenant with slug '{slug}' already exists")
        self.slug = slug


class IdempotencyConflictError(Exception):
    """Raised when idempotency key is reused with different request body."""

    def __init__(self, idempotency_key: str) -> None:
        super().__init__(f"Idempotency key '{idempotency_key}' used with different request")
        self.idempotency_key = idempotency_key


class TenantNotFoundError(Exception):
    """Raised when tenant is not found."""

    def __init__(self, tenant_id: UUID) -> None:
        super().__init__(f"Tenant '{tenant_id}' not found")
        self.tenant_id = tenant_id


class TenantProvisioningService:
    """Service for tenant provisioning with idempotency support."""

    def __init__(
        self,
        event_publisher: EventPublisher,
        idempotency_ttl_hours: int = 24,
    ) -> None:
        self.event_publisher = event_publisher
        self.idempotency_ttl = timedelta(hours=idempotency_ttl_hours)

    def _compute_request_hash(self, request: CreateTenantRequest) -> str:
        """Compute SHA-256 hash of request body for idempotency validation."""
        content = request.model_dump_json(exclude_none=True)
        return hashlib.sha256(content.encode()).hexdigest()

    async def _check_idempotency(
        self,
        session: AsyncSession,
        idempotency_key: str,
        request_hash: str,
    ) -> TenantResponse | None:
        """Check if idempotency key exists and return cached response if valid."""
        result = await session.execute(
            select(IdempotencyKey).where(IdempotencyKey.idempotency_key == idempotency_key)
        )
        existing = result.scalar_one_or_none()

        if existing is None:
            return None

        if existing.request_hash != request_hash:
            raise IdempotencyConflictError(idempotency_key)

        if existing.status == "completed" and existing.response_data:
            logger.info(
                "Returning cached response for idempotency_key=%s",
                idempotency_key,
            )
            return TenantResponse.model_validate(existing.response_data)

        if existing.status == "pending":
            # Another request is in progress
            logger.warning(
                "Concurrent request detected for idempotency_key=%s",
                idempotency_key,
            )

        return None

    async def _store_idempotency_key(
        self,
        session: AsyncSession,
        idempotency_key: str,
        request_hash: str,
        operation: str,
    ) -> IdempotencyKey:
        """Store idempotency key for a new request."""
        key_record = IdempotencyKey(
            idempotency_key=idempotency_key,
            operation=operation,
            request_hash=request_hash,
            status="pending",
            expires_at=datetime.now(timezone.utc) + self.idempotency_ttl,
        )
        session.add(key_record)
        await session.flush()
        return key_record

    async def _complete_idempotency_key(
        self,
        session: AsyncSession,
        key_record: IdempotencyKey,
        resource_id: UUID,
        tenant_id: UUID,
        response_data: dict,
    ) -> None:
        """Mark idempotency key as completed with cached response."""
        key_record.status = "completed"
        key_record.resource_id = resource_id
        key_record.tenant_id = tenant_id
        key_record.response_data = response_data
        await session.flush()

    async def _fail_idempotency_key(
        self,
        session: AsyncSession,
        key_record: IdempotencyKey,
    ) -> None:
        """Mark idempotency key as failed."""
        key_record.status = "failed"
        await session.flush()

    def _build_default_configurations(
        self,
        tenant_id: UUID,
        config: TenantConfiguration,
    ) -> list[TenantConfigDB]:
        """Build database configuration records from tenant config."""
        configs = []

        # Flatten configuration into key-value pairs
        config_items = [
            ("features.skills_framework", {"enabled": config.features.skills_framework}),
            ("features.recommendations", {"enabled": config.features.recommendations}),
            ("features.learning_paths", {"enabled": config.features.learning_paths}),
            ("features.analytics", {"enabled": config.features.analytics}),
            ("limits.max_users", {"value": config.limits.max_users}),
            ("limits.max_organizations", {"value": config.limits.max_organizations}),
            ("limits.api_rate_limit", {"value": config.limits.api_rate_limit}),
            ("retention.audit_logs_days", {"value": config.retention.audit_logs_days}),
            ("retention.analytics_days", {"value": config.retention.analytics_days}),
            ("privacy.data_region", {"value": config.privacy.data_region}),
            ("privacy.gdpr_enabled", {"enabled": config.privacy.gdpr_enabled}),
            ("branding.logo_url", {"value": config.branding.logo_url}),
            ("branding.primary_color", {"value": config.branding.primary_color}),
            ("notifications.email_enabled", {"enabled": config.notifications.email_enabled}),
            ("notifications.webhook_url", {"value": config.notifications.webhook_url}),
        ]

        for key, value in config_items:
            configs.append(
                TenantConfigDB(
                    tenant_id=tenant_id,
                    config_key=key,
                    config_value=value,
                )
            )

        return configs

    async def _create_audit_log(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        actor_id: UUID,
        actor_type: str,
        action: str,
        resource_type: str,
        resource_id: UUID | None = None,
        new_value: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Create an audit log entry."""
        audit_log = TenantAuditLog(
            tenant_id=tenant_id,
            actor_id=actor_id,
            actor_type=actor_type,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            new_value=new_value,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        session.add(audit_log)

    async def create_tenant(
        self,
        session: AsyncSession,
        request: CreateTenantRequest,
        created_by: UUID,
        actor_type: str = "user",
        idempotency_key: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TenantResponse:
        """Create a new tenant with idempotency support.
        
        This method is atomic: tenant and configuration are created together.
        If idempotency_key is provided, duplicate requests return the same response.
        """
        request_hash = self._compute_request_hash(request)
        key_record: IdempotencyKey | None = None

        # Check idempotency if key provided
        if idempotency_key:
            cached = await self._check_idempotency(session, idempotency_key, request_hash)
            if cached:
                return cached

            try:
                key_record = await self._store_idempotency_key(
                    session, idempotency_key, request_hash, "create_tenant"
                )
            except IntegrityError:
                # Key was created by concurrent request
                await session.rollback()
                cached = await self._check_idempotency(session, idempotency_key, request_hash)
                if cached:
                    return cached
                raise IdempotencyConflictError(idempotency_key)

        try:
            # Create tenant record
            tenant = Tenant(
                name=request.name,
                slug=request.slug,
                status=TenantStatus.PROVISIONING,
                tier=request.tier,
                contact_email=request.contact_email,
                billing_email=request.billing_email,
                metadata=request.metadata,
                created_by=created_by,
            )
            session.add(tenant)
            await session.flush()

            # Emit provisioning started event
            await self.event_publisher.publish(
                TenantProvisioningEvent(
                    event_type=EventTypes.TENANT_PROVISIONING_STARTED,
                    tenant_id=tenant.id,
                    payload={
                        "name": tenant.name,
                        "slug": tenant.slug,
                        "tier": tenant.tier.value if isinstance(tenant.tier, TenantTier) else tenant.tier,
                        "created_by": str(created_by),
                    },
                )
            )

            # Create default configuration
            config = TenantConfiguration.for_tier(request.tier)
            config_records = self._build_default_configurations(tenant.id, config)
            for record in config_records:
                session.add(record)

            # Mark as active
            tenant.status = TenantStatus.ACTIVE
            tenant.provisioned_at = datetime.now(timezone.utc)
            await session.flush()

            # Create audit log
            await self._create_audit_log(
                session=session,
                tenant_id=tenant.id,
                actor_id=created_by,
                actor_type=actor_type,
                action="tenant.created",
                resource_type="tenant",
                resource_id=tenant.id,
                new_value={
                    "name": tenant.name,
                    "slug": tenant.slug,
                    "tier": tenant.tier.value if isinstance(tenant.tier, TenantTier) else tenant.tier,
                },
                ip_address=ip_address,
                user_agent=user_agent,
            )

            # Build response
            response = TenantResponse(
                id=tenant.id,
                name=tenant.name,
                slug=tenant.slug,
                status=TenantStatus(tenant.status) if isinstance(tenant.status, str) else tenant.status,
                tier=TenantTier(tenant.tier) if isinstance(tenant.tier, str) else tenant.tier,
                contact_email=tenant.contact_email,
                billing_email=tenant.billing_email,
                metadata=tenant.metadata,
                configuration=config,
                created_at=tenant.created_at,
                updated_at=tenant.updated_at,
                provisioned_at=tenant.provisioned_at,
                created_by=tenant.created_by,
            )

            # Update idempotency key with response
            if key_record:
                await self._complete_idempotency_key(
                    session, key_record, tenant.id, tenant.id, response.model_dump(mode="json")
                )

            await session.commit()

            # Emit provisioned event
            await self.event_publisher.publish(
                TenantProvisioningEvent(
                    event_type=EventTypes.TENANT_PROVISIONED,
                    tenant_id=tenant.id,
                    payload={
                        "name": tenant.name,
                        "slug": tenant.slug,
                        "tier": response.tier.value,
                        "created_by": str(created_by),
                        "provisioned_at": tenant.provisioned_at.isoformat() if tenant.provisioned_at else None,
                    },
                )
            )

            logger.info(
                "Tenant provisioned: id=%s slug=%s tier=%s",
                tenant.id,
                tenant.slug,
                tenant.tier,
            )
            return response

        except IntegrityError as e:
            await session.rollback()
            if "tenants_slug_unique" in str(e) or "slug" in str(e).lower():
                if key_record:
                    await self._fail_idempotency_key(session, key_record)
                    await session.commit()
                raise TenantExistsError(request.slug)
            raise

        except Exception as e:
            await session.rollback()
            if key_record:
                key_record.status = "failed"
                await session.commit()

            # Emit failure event
            await self.event_publisher.publish(
                TenantProvisioningEvent(
                    event_type=EventTypes.TENANT_PROVISIONING_FAILED,
                    tenant_id=UUID("00000000-0000-0000-0000-000000000000"),  # Placeholder
                    payload={
                        "slug": request.slug,
                        "error": str(e),
                        "created_by": str(created_by),
                    },
                )
            )
            raise

    async def get_tenant(
        self,
        session: AsyncSession,
        tenant_id: UUID,
    ) -> TenantResponse:
        """Get tenant by ID with configuration."""
        result = await session.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()

        if not tenant:
            raise TenantNotFoundError(tenant_id)

        # Load configurations
        config_result = await session.execute(
            select(TenantConfigDB).where(TenantConfigDB.tenant_id == tenant_id)
        )
        config_records = config_result.scalars().all()

        # Rebuild configuration from stored values
        config = TenantConfiguration.for_tier(
            TenantTier(tenant.tier) if isinstance(tenant.tier, str) else tenant.tier
        )

        for record in config_records:
            key_parts = record.config_key.split(".")
            if len(key_parts) == 2:
                section, field = key_parts
                section_obj = getattr(config, section, None)
                if section_obj:
                    value = record.config_value.get("value") or record.config_value.get("enabled")
                    if hasattr(section_obj, field):
                        setattr(section_obj, field, value)

        return TenantResponse(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            status=TenantStatus(tenant.status) if isinstance(tenant.status, str) else tenant.status,
            tier=TenantTier(tenant.tier) if isinstance(tenant.tier, str) else tenant.tier,
            contact_email=tenant.contact_email,
            billing_email=tenant.billing_email,
            metadata=tenant.metadata,
            configuration=config,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at,
            provisioned_at=tenant.provisioned_at,
            created_by=tenant.created_by,
        )

    async def get_tenant_by_slug(
        self,
        session: AsyncSession,
        slug: str,
    ) -> TenantResponse:
        """Get tenant by slug."""
        result = await session.execute(
            select(Tenant).where(Tenant.slug == slug)
        )
        tenant = result.scalar_one_or_none()

        if not tenant:
            raise TenantNotFoundError(UUID("00000000-0000-0000-0000-000000000000"))

        return await self.get_tenant(session, tenant.id)
