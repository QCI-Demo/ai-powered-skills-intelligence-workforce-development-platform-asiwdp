"""Tenant-scoped provisioning event publishing."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID, uuid4

EVENT_TYPE = "tenant.provisioned"
EVENT_VERSION = "1.0.0"
EVENT_SOURCE = "asiwdp.tenant-provisioning"
EVENT_TOPIC = "asiwdp.tenants.provisioned"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


@dataclass(slots=True)
class TenantProvisionedEvent:
    """Structured telemetry event emitted after successful tenant creation."""

    event_id: str
    event_type: str
    event_version: str
    tenant_id: str
    timestamp: str
    source: str
    actor: dict[str, Any]
    payload: dict[str, Any]
    correlation_id: str | None = None
    topic: str = EVENT_TOPIC

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        # topic is transport metadata; keep in envelope for bus adapters
        return data

    @property
    def partition_key(self) -> str:
        """Bus partition / routing key — always the provisioned tenant_id."""
        return self.tenant_id


class EventBus(Protocol):
    def publish(self, event: TenantProvisionedEvent) -> None: ...


@dataclass
class InMemoryEventBus:
    """Test / local event bus that retains published events in order."""

    events: list[TenantProvisionedEvent] = field(default_factory=list)

    def publish(self, event: TenantProvisionedEvent) -> None:
        if not event.tenant_id:
            raise ValueError("tenant.provisioned events must be tenant-scoped")
        self.events.append(event)

    def clear(self) -> None:
        self.events.clear()

    def events_for_tenant(self, tenant_id: str | UUID) -> list[TenantProvisionedEvent]:
        tid = str(tenant_id)
        return [e for e in self.events if e.tenant_id == tid]


def build_tenant_provisioned_event(
    *,
    tenant_id: UUID,
    slug: str,
    display_name: str,
    status: str,
    plan_code: str,
    region: str,
    timezone_name: str,
    default_config_keys: list[str],
    actor_subject: str,
    actor_roles: tuple[str, ...] | list[str],
    requesting_tenant_id: str | None,
    idempotency_key: str | None = None,
    correlation_id: str | None = None,
) -> TenantProvisionedEvent:
    return TenantProvisionedEvent(
        event_id=str(uuid4()),
        event_type=EVENT_TYPE,
        event_version=EVENT_VERSION,
        tenant_id=str(tenant_id),
        timestamp=_utcnow_iso(),
        source=EVENT_SOURCE,
        correlation_id=correlation_id,
        actor={
            "subject": actor_subject,
            "requesting_tenant_id": requesting_tenant_id,
            "roles": list(actor_roles),
        },
        payload={
            "slug": slug,
            "display_name": display_name,
            "status": status,
            "plan_code": plan_code,
            "region": region,
            "timezone": timezone_name,
            "default_config_keys": list(default_config_keys),
            "idempotency_key": idempotency_key,
            "replay": False,
        },
    )
