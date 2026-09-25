"""Event publishing for tenant provisioning.

Task: 4a9fb493-572e-4e33-bac6-eeb81ba43ec1
Emit a structured event containing tenantId, timestamp, and provisioning details to the centralized event bus.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from tenant_provisioning.models import TenantProvisionedEvent, TenantResponse

logger = logging.getLogger(__name__)


class EventPublisher(ABC):
    """Abstract base class for event publishing."""

    @abstractmethod
    async def publish(self, event: TenantProvisionedEvent) -> None:
        """Publish a tenant provisioned event."""
        pass


class LoggingEventPublisher(EventPublisher):
    """Event publisher that logs events (for testing/development)."""

    async def publish(self, event: TenantProvisionedEvent) -> None:
        """Log the event for debugging."""
        logger.info(
            "Published event: %s",
            event.model_dump_json(by_alias=True),
        )


class HttpEventPublisher(EventPublisher):
    """Event publisher that sends events to an HTTP event bus.
    
    Task: 4a9fb493-572e-4e33-bac6-eeb81ba43ec1
    """

    def __init__(self, event_bus_url: str) -> None:
        self._event_bus_url = event_bus_url

    async def publish(self, event: TenantProvisionedEvent) -> None:
        """Publish event to HTTP event bus."""
        import httpx

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self._event_bus_url,
                    json=event.model_dump(by_alias=True, mode="json"),
                    headers={
                        "Content-Type": "application/json",
                        "X-Event-Type": event.event_type,
                        "X-Tenant-Id": str(event.tenant_id),
                    },
                    timeout=10.0,
                )
                response.raise_for_status()
                logger.info(
                    "Published event %s for tenant %s",
                    event.event_id,
                    event.tenant_id,
                )
            except httpx.HTTPError as e:
                logger.error(
                    "Failed to publish event %s: %s",
                    event.event_id,
                    str(e),
                )
                raise


class InMemoryEventPublisher(EventPublisher):
    """In-memory event publisher for testing."""

    def __init__(self) -> None:
        self.events: list[TenantProvisionedEvent] = []

    async def publish(self, event: TenantProvisionedEvent) -> None:
        """Store event in memory."""
        self.events.append(event)

    def clear(self) -> None:
        """Clear stored events."""
        self.events.clear()


def create_tenant_provisioned_event(tenant: TenantResponse) -> TenantProvisionedEvent:
    """Create a tenant provisioned event from a tenant response.
    
    Task: 4a9fb493-572e-4e33-bac6-eeb81ba43ec1
    Define event schema and ensure event is tenant-scoped.
    """
    return TenantProvisionedEvent(
        eventType="tenant.provisioned",
        eventId=uuid4(),
        timestamp=datetime.now(timezone.utc),
        tenantId=tenant.id,
        tenantSlug=tenant.slug,
        tenantName=tenant.name,
        createdBy=tenant.created_by,
        configurationVersion=tenant.configuration.version,
        metadata=tenant.metadata,
    )
