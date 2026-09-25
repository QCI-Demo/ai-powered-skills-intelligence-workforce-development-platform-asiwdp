"""Event publishing for tenant provisioning telemetry."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TenantProvisioningEvent:
    """Structured event emitted when a tenant is provisioned.
    
    Schema follows CloudEvents specification with tenant-scoped metadata.
    """

    event_type: str
    tenant_id: UUID
    payload: dict[str, Any]
    event_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "tenant-provisioning-service"
    spec_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to dictionary for publishing."""
        return {
            "specversion": self.spec_version,
            "type": self.event_type,
            "source": self.source,
            "id": str(self.event_id),
            "time": self.timestamp.isoformat(),
            "datacontenttype": "application/json",
            "tenantid": str(self.tenant_id),  # Extension attribute for tenant scoping
            "data": self.payload,
        }

    def to_json(self) -> str:
        """Serialize event to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class EventPublisher(ABC):
    """Abstract base class for event publishing."""

    @abstractmethod
    async def publish(self, event: TenantProvisioningEvent) -> None:
        """Publish an event to the event bus."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close any open connections."""
        pass


class LoggingEventPublisher(EventPublisher):
    """Event publisher that logs events (for development/testing)."""

    async def publish(self, event: TenantProvisioningEvent) -> None:
        """Log the event instead of publishing to a real bus."""
        logger.info(
            "Event published: type=%s tenant_id=%s event_id=%s",
            event.event_type,
            event.tenant_id,
            event.event_id,
        )
        logger.debug("Event payload: %s", event.to_json())

    async def close(self) -> None:
        """No-op for logging publisher."""
        pass


class InMemoryEventPublisher(EventPublisher):
    """In-memory event publisher for testing."""

    def __init__(self) -> None:
        self.events: list[TenantProvisioningEvent] = []

    async def publish(self, event: TenantProvisioningEvent) -> None:
        """Store event in memory."""
        self.events.append(event)
        logger.debug("Event stored in memory: %s", event.event_type)

    async def close(self) -> None:
        """Clear stored events."""
        self.events.clear()

    def get_events_for_tenant(self, tenant_id: UUID) -> list[TenantProvisioningEvent]:
        """Get all events for a specific tenant."""
        return [e for e in self.events if e.tenant_id == tenant_id]

    def clear(self) -> None:
        """Clear all stored events."""
        self.events.clear()


class HttpEventPublisher(EventPublisher):
    """HTTP-based event publisher for production use."""

    def __init__(self, event_bus_url: str, topic: str) -> None:
        self.event_bus_url = event_bus_url.rstrip("/")
        self.topic = topic
        self._client: Any | None = None

    async def _get_client(self) -> Any:
        """Lazy initialization of HTTP client."""
        if self._client is None:
            try:
                import httpx
                self._client = httpx.AsyncClient(timeout=30.0)
            except ImportError:
                raise RuntimeError("httpx is required for HTTP event publishing")
        return self._client

    async def publish(self, event: TenantProvisioningEvent) -> None:
        """Publish event to HTTP endpoint."""
        if not self.event_bus_url:
            logger.warning("Event bus URL not configured, skipping publish")
            return

        client = await self._get_client()
        url = f"{self.event_bus_url}/topics/{self.topic}/events"

        try:
            response = await client.post(
                url,
                json=event.to_dict(),
                headers={
                    "Content-Type": "application/cloudevents+json",
                    "Ce-Type": event.event_type,
                    "Ce-Source": event.source,
                    "Ce-Id": str(event.event_id),
                    "Ce-Tenantid": str(event.tenant_id),
                },
            )
            response.raise_for_status()
            logger.info(
                "Event published successfully: type=%s tenant_id=%s",
                event.event_type,
                event.tenant_id,
            )
        except Exception as e:
            logger.error(
                "Failed to publish event: type=%s tenant_id=%s error=%s",
                event.event_type,
                event.tenant_id,
                str(e),
            )
            raise

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None


# Event type constants
class EventTypes:
    """Constants for tenant provisioning event types."""

    TENANT_PROVISIONING_STARTED = "tenant.provisioning.started"
    TENANT_PROVISIONED = "tenant.provisioned"
    TENANT_PROVISIONING_FAILED = "tenant.provisioning.failed"
    TENANT_ACTIVATED = "tenant.activated"
    TENANT_SUSPENDED = "tenant.suspended"
    TENANT_DEACTIVATED = "tenant.deactivated"
    TENANT_CONFIGURATION_UPDATED = "tenant.configuration.updated"


def create_event_publisher(event_bus_url: str | None, topic: str) -> EventPublisher:
    """Factory function to create the appropriate event publisher."""
    if event_bus_url:
        return HttpEventPublisher(event_bus_url, topic)
    return LoggingEventPublisher()
