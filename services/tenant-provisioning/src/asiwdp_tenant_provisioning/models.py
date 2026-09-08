"""Domain models for tenant provisioning."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4


DEFAULT_FEATURE_FLAGS: dict[str, bool] = {
    "skills": True,
    "learning_paths": True,
    "analytics": True,
    "recommendations": True,
}

DEFAULT_PRIVACY: dict[str, Any] = {
    "retention_days": 365,
    "consent_required": True,
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def build_default_config_blob(
    *,
    locale: str = "en-US",
    timezone_name: str = "UTC",
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the default configuration document applied at provision time."""
    defaults: dict[str, Any] = {
        "features": dict(DEFAULT_FEATURE_FLAGS),
        "privacy": dict(DEFAULT_PRIVACY),
    }
    if overrides:
        features = overrides.get("features")
        if isinstance(features, dict):
            defaults["features"].update({k: bool(v) for k, v in features.items()})
        privacy = overrides.get("privacy")
        if isinstance(privacy, dict):
            defaults["privacy"].update(privacy)
    return {
        "defaults": defaults,
        "locale": locale,
        "timezone": timezone_name,
        "metering_enabled": True,
        "gdpr_enabled": True,
        "ccpa_enabled": True,
        "schema_version": 1,
    }


@dataclass
class TenantRecord:
    tenant_id: UUID
    slug: str
    display_name: str
    status: str
    plan_code: str
    data_residency: str
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
    provisioned_at: datetime | None


@dataclass
class TenantConfiguration:
    tenant_id: UUID
    defaults: dict[str, Any]
    locale: str
    timezone: str
    metering_enabled: bool
    gdpr_enabled: bool
    ccpa_enabled: bool
    schema_version: int
    created_at: datetime
    updated_at: datetime


@dataclass
class TenantMetadataEntry:
    id: UUID
    tenant_id: UUID
    meta_key: str
    meta_value: dict[str, Any]
    created_by: str | None
    created_at: datetime
    updated_at: datetime


@dataclass
class IdempotencyRecord:
    idempotency_key: str
    tenant_id: UUID
    request_hash: str
    response_status: int
    response_body: dict[str, Any]
    created_at: datetime
    expires_at: datetime


@dataclass
class ProvisionedTenant:
    tenant: TenantRecord
    configuration: TenantConfiguration
    metadata: list[TenantMetadataEntry] = field(default_factory=list)
    created: bool = True

    def to_response_dict(self) -> dict[str, Any]:
        return {
            "tenantId": str(self.tenant.tenant_id),
            "slug": self.tenant.slug,
            "displayName": self.tenant.display_name,
            "status": self.tenant.status,
            "planCode": self.tenant.plan_code,
            "dataResidency": self.tenant.data_residency,
            "createdBy": str(self.tenant.created_by) if self.tenant.created_by else None,
            "createdAt": self.tenant.created_at.isoformat().replace("+00:00", "Z"),
            "updatedAt": self.tenant.updated_at.isoformat().replace("+00:00", "Z"),
            "provisionedAt": (
                self.tenant.provisioned_at.isoformat().replace("+00:00", "Z")
                if self.tenant.provisioned_at
                else None
            ),
            "configuration": {
                "locale": self.configuration.locale,
                "timezone": self.configuration.timezone,
                "meteringEnabled": self.configuration.metering_enabled,
                "gdprEnabled": self.configuration.gdpr_enabled,
                "ccpaEnabled": self.configuration.ccpa_enabled,
                "schemaVersion": self.configuration.schema_version,
                "defaults": self.configuration.defaults,
            },
            "metadata": [
                {
                    "key": m.meta_key,
                    "value": m.meta_value,
                }
                for m in self.metadata
            ],
            "created": self.created,
        }


def new_tenant_id() -> UUID:
    return uuid4()
