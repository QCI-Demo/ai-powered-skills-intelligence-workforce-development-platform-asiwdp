"""Tenant provisioning event schemas and publisher."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ProvisioningEventType(str, Enum):
    """Types of tenant provisioning events."""

    PROVISIONING_STARTED = "tenant.provisioning.started"
    PROVISIONING_COMPLETED = "tenant.provisioning.completed"
    PROVISIONING_FAILED = "tenant.provisioning.failed"
    CONFIGURATION_INITIALIZED = "tenant.configuration.initialized"
    STATUS_CHANGED = "tenant.status.changed"
    TIER_CHANGED = "tenant.tier.changed"


class EventDeliveryStatus(str, Enum):
    """Event delivery status."""

    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRY = "retry"


class TenantProvisioningEvent(BaseModel):
    """Structured event for tenant provisioning telemetry."""

    event_id: UUID = Field(default_factory=uuid4, description="Unique event identifier")
    event_type: ProvisioningEventType = Field(..., description="Type of event")
    tenant_id: UUID = Field(..., description="Tenant the event relates to")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Event timestamp (UTC)",
    )
    payload: dict[str, Any] = Field(default_factory=dict, description="Event details")
    source: str = Field(
        default="tenant-provisioning-service",
        description="Service that emitted the event",
    )
    version: str = Field(default="1.0.0", description="Event schema version")
    correlation_id: str | None = Field(
        None, description="Request correlation ID for tracing"
    )

    def to_event_bus_format(self) -> dict[str, Any]:
        """Format event for centralized event bus."""
        return {
            "id": str(self.event_id),
            "type": self.event_type.value,
            "source": self.source,
            "time": self.timestamp.isoformat(),
            "datacontenttype": "application/json",
            "subject": f"tenant/{self.tenant_id}",
            "data": {
                "tenant_id": str(self.tenant_id),
                "event_type": self.event_type.value,
                "timestamp": self.timestamp.isoformat(),
                "correlation_id": self.correlation_id,
                **self.payload,
            },
            "specversion": "1.0",
        }


class EventPublisher:
    """Publishes tenant provisioning events to the event bus."""

    def __init__(self, event_bus_url: str | None = None):
        """Initialize the event publisher.

        Args:
            event_bus_url: URL of the centralized event bus. If None, events
                are logged locally (useful for testing).
        """
        self._event_bus_url = event_bus_url
        self._pending_events: list[TenantProvisioningEvent] = []

    async def publish(self, event: TenantProvisioningEvent) -> bool:
        """Publish an event to the event bus.

        Args:
            event: The event to publish.

        Returns:
            True if published successfully, False otherwise.
        """
        import logging

        logger = logging.getLogger(__name__)

        event_data = event.to_event_bus_format()

        if self._event_bus_url:
            try:
                import httpx

                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        self._event_bus_url,
                        json=event_data,
                        headers={"Content-Type": "application/cloudevents+json"},
                    )
                    response.raise_for_status()
                    logger.info(
                        "Published event %s for tenant %s",
                        event.event_type.value,
                        event.tenant_id,
                    )
                    return True
            except Exception as exc:
                logger.error(
                    "Failed to publish event %s: %s", event.event_type.value, exc
                )
                self._pending_events.append(event)
                return False
        else:
            # Local logging mode for development/testing
            logger.info(
                "Event (local): %s - tenant=%s payload=%s",
                event.event_type.value,
                event.tenant_id,
                event.payload,
            )
            return True

    async def publish_provisioning_started(
        self,
        tenant_id: UUID,
        *,
        name: str,
        tier: str,
        provisioned_by: UUID | None,
        correlation_id: str | None = None,
    ) -> TenantProvisioningEvent:
        """Emit a provisioning started event."""
        event = TenantProvisioningEvent(
            event_type=ProvisioningEventType.PROVISIONING_STARTED,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            payload={
                "name": name,
                "tier": tier,
                "provisioned_by": str(provisioned_by) if provisioned_by else None,
            },
        )
        await self.publish(event)
        return event

    async def publish_provisioning_completed(
        self,
        tenant_id: UUID,
        *,
        name: str,
        slug: str,
        tier: str,
        config_count: int,
        provisioned_by: UUID | None,
        correlation_id: str | None = None,
    ) -> TenantProvisioningEvent:
        """Emit a provisioning completed event."""
        event = TenantProvisioningEvent(
            event_type=ProvisioningEventType.PROVISIONING_COMPLETED,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            payload={
                "name": name,
                "slug": slug,
                "tier": tier,
                "configuration_count": config_count,
                "provisioned_by": str(provisioned_by) if provisioned_by else None,
            },
        )
        await self.publish(event)
        return event

    async def publish_provisioning_failed(
        self,
        tenant_id: UUID,
        *,
        error: str,
        error_code: str,
        correlation_id: str | None = None,
    ) -> TenantProvisioningEvent:
        """Emit a provisioning failed event."""
        event = TenantProvisioningEvent(
            event_type=ProvisioningEventType.PROVISIONING_FAILED,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            payload={
                "error": error,
                "error_code": error_code,
            },
        )
        await self.publish(event)
        return event

    async def publish_configuration_initialized(
        self,
        tenant_id: UUID,
        *,
        config_count: int,
        tier: str,
        correlation_id: str | None = None,
    ) -> TenantProvisioningEvent:
        """Emit a configuration initialized event."""
        event = TenantProvisioningEvent(
            event_type=ProvisioningEventType.CONFIGURATION_INITIALIZED,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            payload={
                "configuration_count": config_count,
                "tier": tier,
            },
        )
        await self.publish(event)
        return event


# Singleton publisher instance (configured at app startup)
_publisher: EventPublisher | None = None


def get_event_publisher() -> EventPublisher:
    """Get the configured event publisher instance."""
    global _publisher
    if _publisher is None:
        import os

        event_bus_url = os.environ.get("ASIWDP_EVENT_BUS_URL")
        _publisher = EventPublisher(event_bus_url)
    return _publisher


def set_event_publisher(publisher: EventPublisher) -> None:
    """Set the event publisher instance (for testing)."""
    global _publisher
    _publisher = publisher
