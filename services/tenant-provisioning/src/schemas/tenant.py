"""Pydantic schemas for tenant provisioning requests and responses."""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TenantStatus(str, Enum):
    """Tenant lifecycle status."""

    PROVISIONING = "provisioning"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEPROVISIONING = "deprovisioning"
    DELETED = "deleted"


class TenantTier(str, Enum):
    """Tenant subscription tier."""

    FREE = "free"
    STANDARD = "standard"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class CreateTenantRequest(BaseModel):
    """Request payload for creating a new tenant."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unique tenant name",
        examples=["Acme Corporation"],
    )
    slug: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="URL-safe identifier (lowercase, alphanumeric, hyphens)",
        examples=["acme-corp"],
    )
    display_name: str | None = Field(
        None,
        max_length=255,
        description="Optional friendly display name",
        examples=["Acme Corp"],
    )
    tier: TenantTier = Field(
        TenantTier.STANDARD,
        description="Subscription tier",
    )
    contact_email: str = Field(
        ...,
        max_length=255,
        description="Primary contact email",
        examples=["admin@acme.example.com"],
    )
    owner_user_id: UUID | None = Field(
        None,
        description="UUID of the initial admin user",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Extensible attributes",
    )

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        pattern = r"^[a-z0-9][a-z0-9-]*[a-z0-9]$"
        if not re.match(pattern, v):
            raise ValueError(
                "Slug must be lowercase alphanumeric with hyphens, "
                "starting and ending with alphanumeric characters"
            )
        return v

    @field_validator("contact_email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
        if not re.match(pattern, v):
            raise ValueError("Invalid email format")
        return v.lower()


class TenantResponse(BaseModel):
    """Response payload for tenant operations."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    tenant_id: UUID = Field(..., description="Unique tenant identifier")
    name: str = Field(..., description="Tenant name")
    slug: str = Field(..., description="URL-safe identifier")
    display_name: str | None = Field(None, description="Friendly display name")
    status: TenantStatus = Field(..., description="Lifecycle status")
    tier: TenantTier = Field(..., description="Subscription tier")
    owner_user_id: UUID | None = Field(None, description="Initial admin user ID")
    contact_email: str = Field(..., description="Primary contact email")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Custom attributes")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    provisioned_at: datetime | None = Field(None, description="Provisioning completion time")
    provisioned_by: UUID | None = Field(None, description="User who provisioned")


class TenantProvisioningResponse(BaseModel):
    """Response for tenant provisioning endpoint."""

    tenant: TenantResponse = Field(..., description="Created tenant details")
    idempotent: bool = Field(
        False,
        description="True if response was retrieved from idempotency cache",
    )
    message: str = Field(..., description="Human-readable status message")


class ConfigurationValue(BaseModel):
    """Individual configuration entry."""

    config_id: UUID = Field(..., description="Configuration entry ID")
    tenant_id: UUID = Field(..., description="Owning tenant ID")
    config_key: str = Field(..., description="Configuration key")
    config_value: Any = Field(..., description="Configuration value")
    is_default: bool = Field(True, description="Whether using platform default")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class TenantConfigurationResponse(BaseModel):
    """Full tenant configuration response."""

    tenant_id: UUID = Field(..., description="Tenant ID")
    configurations: list[ConfigurationValue] = Field(
        ..., description="All configuration entries"
    )


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict[str, Any] | None = Field(None, description="Additional error details")
