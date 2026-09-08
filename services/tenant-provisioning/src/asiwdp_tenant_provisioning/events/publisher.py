"""Tenant-scoped event bus publishing for provisioning telemetry."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

import jsonschema

from asiwdp_tenant_provisioning.models import ProvisionedTenant

EVENT_TYPE = "com.asiwdp.tenant.provisioned"
EVENT_SOURCE = "asiwdp.tenant-provisioning"
EVENT_CHANNEL = "asiwdp.telemetry.tenant-events"

_SCHEMA_PATH = Path(__file__).with_name("tenant_provisioned.schema.json")
_SCHEMA: dict[str, Any] | None = None


def _load_schema() -> dict[str, Any]:
    global _SCHEMA
    if _SCHEMA is None:
        _SCHEMA = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return _SCHEMA


def build_tenant_provisioned_event(
    provisioned: ProvisionedTenant,
    *,
    requesting_tenant_id: str | None,
    idempotency_key: str,
    event_id: str | None = None,
    timestamp: datetime | None = None,
) -> dict[str, Any]:
    """Build a CloudEvents-style, tenant-scoped provisioning event."""
    tenant = provisioned.tenant
    cfg = provisioned.configuration
    ts = timestamp or datetime.now(timezone.utc)
    time_str = ts.isoformat().replace("+00:00", "Z")
    tenant_id = str(tenant.tenant_id)
    event = {
        "specversion": "1.0",
        "id": event_id or str(uuid4()),
        "type": EVENT_TYPE,
        "source": EVENT_SOURCE,
        "time": time_str,
        "subject": f"tenant/{tenant_id}",
        "datacontenttype": "application/json",
        "tenantId": tenant_id,
        "data": {
            "tenantId": tenant_id,
            "slug": tenant.slug,
            "displayName": tenant.display_name,
            "status": tenant.status,
            "planCode": tenant.plan_code,
            "dataResidency": tenant.data_residency,
            "provisionedAt": (
                tenant.provisioned_at.isoformat().replace("+00:00", "Z")
                if tenant.provisioned_at
                else time_str
            ),
            "createdBy": str(tenant.created_by) if tenant.created_by else None,
            "requestingTenantId": requesting_tenant_id,
            "idempotencyKey": idempotency_key,
            "configuration": {
                "locale": cfg.locale,
                "timezone": cfg.timezone,
                "schemaVersion": cfg.schema_version,
                "meteringEnabled": cfg.metering_enabled,
                "gdprEnabled": cfg.gdpr_enabled,
                "ccpaEnabled": cfg.ccpa_enabled,
            },
        },
    }
    jsonschema.validate(instance=event, schema=_load_schema())
    return event


class EventBus(Protocol):
    def publish(self, channel: str, event: dict[str, Any], *, partition_key: str) -> None:
        ...


@dataclass
class InMemoryEventBus:
    """Test/local event bus that records published messages."""

    messages: list[dict[str, Any]] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def publish(
        self, channel: str, event: dict[str, Any], *, partition_key: str
    ) -> None:
        with self._lock:
            self.messages.append(
                {
                    "channel": channel,
                    "partition_key": partition_key,
                    "event": event,
                }
            )

    def clear(self) -> None:
        with self._lock:
            self.messages.clear()

    def events_for_tenant(self, tenant_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return [
                m["event"]
                for m in self.messages
                if m.get("partition_key") == tenant_id
                or m.get("event", {}).get("tenantId") == tenant_id
            ]


class TenantProvisioningPublisher:
    """Publishes tenant.provisioned events after successful creation."""

    def __init__(self, bus: EventBus, *, channel: str = EVENT_CHANNEL) -> None:
        self._bus = bus
        self._channel = channel

    def publish_provisioned(
        self,
        provisioned: ProvisionedTenant,
        *,
        requesting_tenant_id: str | None,
        idempotency_key: str,
    ) -> dict[str, Any]:
        event = build_tenant_provisioned_event(
            provisioned,
            requesting_tenant_id=requesting_tenant_id,
            idempotency_key=idempotency_key,
        )
        tenant_id = str(provisioned.tenant.tenant_id)
        self._bus.publish(self._channel, event, partition_key=tenant_id)
        return event
