"""Event publishing for tenant provisioning telemetry."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from tenant_provisioning.config import get_settings
from tenant_provisioning.entities import ProvisioningEvent
from tenant_provisioning.models import EventStatus, PlanTier, TenantProvisioningEvent

logger = logging.getLogger(__name__)


class EventBusProtocol(Protocol):
    """Protocol for event bus implementations."""

    async def publish(self, topic: str, event: dict[str, Any]) -> bool:
        """Publish event to topic. Returns True if successful."""
        ...


class LoggingEventBus:
    """Event bus implementation that logs events (for development/testing)."""

    async def publish(self, topic: str, event: dict[str, Any]) -> bool:
        """Log the event for debugging."""
        logger.info(
            "Event published",
            extra={"topic": topic, "event": json.dumps(event, default=str)},
        )
        return True


class EventPublisher:
    """Publisher for tenant provisioning events."""

    def __init__(
        self,
        session: AsyncSession,
        event_bus: EventBusProtocol | None = None,
    ) -> None:
        self._session = session
        self._settings = get_settings()
        self._event_bus = event_bus or LoggingEventBus()

    async def publish_tenant_provisioned(
        self,
        tenant_id: UUID,
        tenant_name: str,
        plan_tier: PlanTier,
        created_by: str,
        metadata: dict[str, Any] | None = None,
    ) -> UUID:
        """Publish tenant.provisioned event.

        Stores event in database and publishes to event bus.
        Returns the event ID.
        """
        event = TenantProvisioningEvent(
            event_id=uuid4(),
            event_type="tenant.provisioned",
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            plan_tier=plan_tier,
            created_by=created_by,
            timestamp=datetime.now(timezone.utc),
            metadata=metadata or {},
        )

        payload = event.to_event_payload()

        # Store event in database
        db_event = ProvisioningEvent(
            event_id=event.event_id,
            tenant_id=tenant_id,
            event_type=event.event_type,
            event_payload=payload,
            status=EventStatus.PENDING,
        )
        self._session.add(db_event)
        await self._session.flush()

        # Publish to event bus
        try:
            success = await self._event_bus.publish(
                self._settings.event_bus_topic,
                payload,
            )
            if success:
                db_event.status = EventStatus.PUBLISHED
                db_event.published_at = datetime.now(timezone.utc)
            else:
                db_event.status = EventStatus.FAILED
        except Exception as e:
            logger.exception("Failed to publish event: %s", e)
            db_event.status = EventStatus.FAILED

        await self._session.flush()
        return event.event_id

    async def publish_tenant_updated(
        self,
        tenant_id: UUID,
        tenant_name: str,
        changes: dict[str, Any],
        updated_by: str,
    ) -> UUID:
        """Publish tenant.updated event."""
        event_id = uuid4()
        payload = {
            "event_id": str(event_id),
            "event_type": "tenant.updated",
            "tenant_id": str(tenant_id),
            "tenant_name": tenant_name,
            "changes": changes,
            "updated_by": updated_by,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        db_event = ProvisioningEvent(
            event_id=event_id,
            tenant_id=tenant_id,
            event_type="tenant.updated",
            event_payload=payload,
            status=EventStatus.PENDING,
        )
        self._session.add(db_event)
        await self._session.flush()

        try:
            success = await self._event_bus.publish(
                self._settings.event_bus_topic,
                payload,
            )
            db_event.status = EventStatus.PUBLISHED if success else EventStatus.FAILED
            if success:
                db_event.published_at = datetime.now(timezone.utc)
        except Exception as e:
            logger.exception("Failed to publish event: %s", e)
            db_event.status = EventStatus.FAILED

        await self._session.flush()
        return event_id

    async def publish_tenant_deprovisioned(
        self,
        tenant_id: UUID,
        tenant_name: str,
        deprovisioned_by: str,
        reason: str | None = None,
    ) -> UUID:
        """Publish tenant.deprovisioned event."""
        event_id = uuid4()
        payload = {
            "event_id": str(event_id),
            "event_type": "tenant.deprovisioned",
            "tenant_id": str(tenant_id),
            "tenant_name": tenant_name,
            "deprovisioned_by": deprovisioned_by,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        db_event = ProvisioningEvent(
            event_id=event_id,
            tenant_id=tenant_id,
            event_type="tenant.deprovisioned",
            event_payload=payload,
            status=EventStatus.PENDING,
        )
        self._session.add(db_event)
        await self._session.flush()

        try:
            success = await self._event_bus.publish(
                self._settings.event_bus_topic,
                payload,
            )
            db_event.status = EventStatus.PUBLISHED if success else EventStatus.FAILED
            if success:
                db_event.published_at = datetime.now(timezone.utc)
        except Exception as e:
            logger.exception("Failed to publish event: %s", e)
            db_event.status = EventStatus.FAILED

        await self._session.flush()
        return event_id
