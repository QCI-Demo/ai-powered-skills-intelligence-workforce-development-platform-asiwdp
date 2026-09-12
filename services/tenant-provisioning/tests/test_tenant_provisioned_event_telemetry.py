"""Unit tests for tenant.provisioned telemetry event schema and publishing."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import jsonschema
import pytest

from asiwdp_tenant_provisioning.events.publisher import (
    EVENT_CHANNEL,
    EVENT_SOURCE,
    EVENT_TYPE,
    InMemoryEventBus,
    TenantProvisioningPublisher,
    _assert_tenant_scoped,
    build_tenant_provisioned_event,
)
from asiwdp_tenant_provisioning.models import (
    ProvisionedTenant,
    TenantConfiguration,
    TenantRecord,
)

CONTRACT_SCHEMA = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "telemetry"
    / "v1"
    / "tenant-provisioned.schema.json"
)
PACKAGE_SCHEMA = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "asiwdp_tenant_provisioning"
    / "events"
    / "tenant_provisioned.schema.json"
)


def _provisioned(
    *,
    tenant_id: UUID | None = None,
    slug: str = "acme-corp",
) -> ProvisionedTenant:
    tid = tenant_id or uuid4()
    now = datetime(2026, 9, 11, 22, 0, 0, tzinfo=timezone.utc)
    tenant = TenantRecord(
        tenant_id=tid,
        slug=slug,
        display_name="Acme Corp",
        status="active",
        plan_code="standard",
        data_residency="us-east",
        created_by=UUID("11111111-1111-1111-1111-111111111111"),
        created_at=now,
        updated_at=now,
        provisioned_at=now,
    )
    configuration = TenantConfiguration(
        tenant_id=tid,
        defaults={"features": {"skills": True}, "privacy": {"retention_days": 365}},
        locale="en-US",
        timezone="UTC",
        metering_enabled=True,
        gdpr_enabled=True,
        ccpa_enabled=True,
        schema_version=1,
        created_at=now,
        updated_at=now,
    )
    return ProvisionedTenant(tenant=tenant, configuration=configuration, created=True)


class TestEventSchema:
    def test_contract_and_package_schemas_align(self) -> None:
        import json

        contract = json.loads(CONTRACT_SCHEMA.read_text(encoding="utf-8"))
        package = json.loads(PACKAGE_SCHEMA.read_text(encoding="utf-8"))
        assert contract["required"] == package["required"]
        assert contract["properties"]["type"] == package["properties"]["type"]
        assert (
            contract["properties"]["data"]["required"]
            == package["properties"]["data"]["required"]
        )
        assert "timestamp" in contract["properties"]["data"]["properties"]
        assert "timestamp" in package["properties"]["data"]["properties"]
        assert "tenantId" in contract["required"]
        assert "time" in contract["required"]

    def test_built_event_contains_tenant_id_timestamp_and_details(self) -> None:
        provisioned = _provisioned()
        event = build_tenant_provisioned_event(
            provisioned,
            requesting_tenant_id="22222222-2222-2222-2222-222222222222",
            idempotency_key="prov-telemetry-0001",
            event_id="evt-fixed-id",
            timestamp=datetime(2026, 9, 11, 22, 5, 0, tzinfo=timezone.utc),
        )

        tenant_id = str(provisioned.tenant.tenant_id)
        assert event["type"] == EVENT_TYPE
        assert event["source"] == EVENT_SOURCE
        assert event["tenantId"] == tenant_id
        assert event["time"] == "2026-09-11T22:05:00Z"
        assert event["data"]["tenantId"] == tenant_id
        assert event["data"]["timestamp"] == "2026-09-11T22:00:00Z"
        assert event["data"]["provisionedAt"] == event["data"]["timestamp"]
        assert event["data"]["slug"] == "acme-corp"
        assert event["data"]["configuration"]["locale"] == "en-US"
        assert event["data"]["idempotencyKey"] == "prov-telemetry-0001"
        assert event["subject"] == f"tenant/{tenant_id}"

        import json

        schema = json.loads(PACKAGE_SCHEMA.read_text(encoding="utf-8"))
        jsonschema.validate(instance=event, schema=schema)


class TestTenantScopedPublishing:
    def test_publish_uses_tenant_partition_key(self) -> None:
        bus = InMemoryEventBus()
        publisher = TenantProvisioningPublisher(bus)
        provisioned = _provisioned()

        event = publisher.publish_provisioned(
            provisioned,
            requesting_tenant_id=None,
            idempotency_key="prov-telemetry-0002",
        )

        assert len(bus.messages) == 1
        message = bus.messages[0]
        tenant_id = str(provisioned.tenant.tenant_id)
        assert message["channel"] == EVENT_CHANNEL
        assert message["partition_key"] == tenant_id
        assert message["event"]["tenantId"] == tenant_id
        assert message["event"] is event
        assert bus.events_for_tenant(tenant_id) == [event]

    def test_assert_tenant_scoped_rejects_mismatched_partition(self) -> None:
        provisioned = _provisioned()
        event = build_tenant_provisioned_event(
            provisioned,
            requesting_tenant_id=None,
            idempotency_key="prov-telemetry-0003",
        )
        with pytest.raises(ValueError, match="partition_key"):
            _assert_tenant_scoped(event, partition_key=str(uuid4()))

    def test_events_isolated_per_tenant(self) -> None:
        bus = InMemoryEventBus()
        publisher = TenantProvisioningPublisher(bus)
        alpha = _provisioned(slug="alpha")
        beta = _provisioned(slug="beta")

        publisher.publish_provisioned(
            alpha, requesting_tenant_id=None, idempotency_key="k-alpha"
        )
        publisher.publish_provisioned(
            beta, requesting_tenant_id=None, idempotency_key="k-beta"
        )

        alpha_id = str(alpha.tenant.tenant_id)
        beta_id = str(beta.tenant.tenant_id)
        assert len(bus.messages) == 2
        assert len(bus.events_for_tenant(alpha_id)) == 1
        assert len(bus.events_for_tenant(beta_id)) == 1
        assert bus.events_for_tenant(alpha_id)[0]["data"]["slug"] == "alpha"
        assert bus.events_for_tenant(beta_id)[0]["data"]["slug"] == "beta"
