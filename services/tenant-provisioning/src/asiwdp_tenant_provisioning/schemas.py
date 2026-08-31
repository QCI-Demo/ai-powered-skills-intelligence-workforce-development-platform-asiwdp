"""Request / response validation schemas for tenant provisioning."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

_SLUG_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,126}[a-z0-9])?$")


class TenantCreateRequest(BaseModel):
    """Payload for POST /api/tenants."""

    model_config = ConfigDict(extra="forbid")

    slug: str = Field(..., min_length=1, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=255)
    plan_code: str = Field(default="standard", min_length=1, max_length=64)
    region: str = Field(default="us-east-1", min_length=1, max_length=64)
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    contact: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _SLUG_RE.match(normalized):
            raise ValueError(
                "slug must be lowercase alphanumeric with optional hyphens "
                "(1–128 chars, cannot start/end with hyphen)"
            )
        return normalized

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("display_name must not be blank")
        return cleaned


class ConfigurationItem(BaseModel):
    config_key: str
    config_value: Any
    is_default: bool = True
    version: int = 1


class MetadataItem(BaseModel):
    meta_key: str
    meta_value: dict[str, Any]


class TenantResponse(BaseModel):
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
    configuration: list[ConfigurationItem] = Field(default_factory=list)
    metadata: list[MetadataItem] = Field(default_factory=list)
    idempotent_replay: bool = False


class ErrorResponse(BaseModel):
    error: str
    message: str
