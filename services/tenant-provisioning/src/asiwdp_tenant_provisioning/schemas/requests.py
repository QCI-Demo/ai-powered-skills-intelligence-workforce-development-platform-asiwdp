"""Pydantic request/response schemas for tenant provisioning."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")


class TenantConfigurationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    locale: str | None = Field(default=None, max_length=32)
    timezone: str | None = Field(default=None, max_length=64)
    features: dict[str, bool] | None = None
    privacy: dict[str, Any] | None = None
    metering_enabled: bool | None = Field(default=None, alias="meteringEnabled")
    gdpr_enabled: bool | None = Field(default=None, alias="gdprEnabled")
    ccpa_enabled: bool | None = Field(default=None, alias="ccpaEnabled")


class TenantProvisionRequest(BaseModel):
    """Payload for POST /api/tenants."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    slug: str = Field(min_length=2, max_length=64)
    display_name: str = Field(min_length=1, max_length=255, alias="displayName")
    plan_code: str = Field(default="standard", max_length=64, alias="planCode")
    data_residency: str = Field(
        default="us-east", max_length=64, alias="dataResidency"
    )
    configuration: TenantConfigurationInput | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _SLUG_RE.match(normalized):
            raise ValueError(
                "slug must be lowercase alphanumeric with hyphens "
                "(2-64 chars, start/end alphanumeric)"
            )
        return normalized

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > 50:
            raise ValueError("metadata may contain at most 50 keys")
        for key in value:
            if not isinstance(key, str) or not key or len(key) > 128:
                raise ValueError("metadata keys must be non-empty strings <= 128 chars")
        return value


class TenantProvisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    tenant_id: str = Field(alias="tenantId")
    slug: str
    display_name: str = Field(alias="displayName")
    status: str
    plan_code: str = Field(alias="planCode")
    data_residency: str = Field(alias="dataResidency")
    created_by: str | None = Field(default=None, alias="createdBy")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    provisioned_at: str | None = Field(default=None, alias="provisionedAt")
    configuration: dict[str, Any]
    metadata: list[dict[str, Any]]
    created: bool
