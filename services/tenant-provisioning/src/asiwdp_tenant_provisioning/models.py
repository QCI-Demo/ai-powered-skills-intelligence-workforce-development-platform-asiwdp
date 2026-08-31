"""Domain models for tenant provisioning."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class TenantRecord:
    tenant_id: UUID
    slug: str
    display_name: str
    status: str
    plan_code: str
    region: str
    timezone: str
    contact: dict[str, Any]
    provisioned_at: datetime
    created_at: datetime
    updated_at: datetime
    created_by: str


@dataclass(slots=True)
class ConfigurationRecord:
    id: UUID
    tenant_id: UUID
    config_key: str
    config_value: Any
    is_default: bool
    version: int
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class MetadataRecord:
    id: UUID
    tenant_id: UUID
    meta_key: str
    meta_value: dict[str, Any]
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class IdempotencyRecord:
    id: UUID
    idempotency_key: str
    requesting_tenant_id: UUID | None
    created_tenant_id: UUID
    request_hash: str
    response_status: int
    response_body: dict[str, Any]
    created_at: datetime
    expires_at: datetime


@dataclass(slots=True)
class ProvisionResult:
    tenant: TenantRecord
    configuration: list[ConfigurationRecord] = field(default_factory=list)
    metadata: list[MetadataRecord] = field(default_factory=list)
    created: bool = True
    idempotent_replay: bool = False
