"""Pydantic models for tenant provisioning API."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FeatureFlags(BaseModel):
    """Feature toggle settings for a tenant."""

    model_config = ConfigDict(extra="allow")

    ai_recommendations: bool = Field(default=True, alias="aiRecommendations")
    advanced_analytics: bool = Field(default=False, alias="advancedAnalytics")
    custom_branding: bool = Field(default=False, alias="customBranding")
    sso_enabled: bool = Field(default=False, alias="ssoEnabled")
    api_access: bool = Field(default=True, alias="apiAccess")


class UsageLimits(BaseModel):
    """Usage limits for a tenant."""

    max_users: int = Field(default=50, alias="maxUsers", ge=1)
    max_organizations: int = Field(default=5, alias="maxOrganizations", ge=1)
    max_skills: int = Field(default=500, alias="maxSkills", ge=1)
    max_learning_paths: int = Field(default=100, alias="maxLearningPaths", ge=1)
    storage_quota_mb: int = Field(default=1024, alias="storageQuotaMb", ge=0)
    api_rate_limit_per_minute: int = Field(default=1000, alias="apiRateLimitPerMinute", ge=1)


class Branding(BaseModel):
    """Branding customization settings."""

    logo_url: str | None = Field(default=None, alias="logoUrl")
    favicon_url: str | None = Field(default=None, alias="faviconUrl")
    primary_color: str = Field(default="#1976D2", alias="primaryColor")
    secondary_color: str = Field(default="#424242", alias="secondaryColor")
    custom_css: str | None = Field(default=None, alias="customCss")

    @field_validator("primary_color", "secondary_color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        if not re.match(r"^#[0-9A-Fa-f]{6}$", v):
            raise ValueError("Color must be a valid hex color code (e.g., #1976D2)")
        return v.upper()


class IntegrationConfig(BaseModel):
    """Integration provider configuration."""

    provider: str
    enabled: bool = False


class Integrations(BaseModel):
    """Third-party integration configurations."""

    sso: IntegrationConfig | None = None
    lms: IntegrationConfig | None = None


class TenantConfiguration(BaseModel):
    """Complete tenant configuration."""

    model_config = ConfigDict(populate_by_name=True)

    feature_flags: FeatureFlags = Field(default_factory=FeatureFlags, alias="featureFlags")
    limits: UsageLimits = Field(default_factory=UsageLimits)
    branding: Branding = Field(default_factory=Branding)
    integrations: Integrations = Field(default_factory=Integrations)
    version: int = Field(default=1, ge=1)

    @classmethod
    def default(cls) -> TenantConfiguration:
        """Create default configuration for new tenants."""
        return cls()


class CreateTenantRequest(BaseModel):
    """Request body for creating a new tenant."""

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=255, description="Tenant display name")
    slug: str = Field(
        ...,
        min_length=2,
        max_length=128,
        pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$",
        description="URL-safe unique tenant identifier",
    )
    metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Optional key-value metadata",
    )
    configuration: TenantConfiguration | None = Field(
        default=None,
        description="Optional custom configuration (defaults applied if not provided)",
    )

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if "--" in v:
            raise ValueError("Slug cannot contain consecutive hyphens")
        return v.lower()


class TenantResponse(BaseModel):
    """Response model for tenant operations."""

    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    name: str
    slug: str
    status: str
    configuration: TenantConfiguration
    metadata: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")
    created_by: str = Field(alias="createdBy")


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    message: str
    details: dict[str, Any] | None = None


class TenantProvisionedEvent(BaseModel):
    """Event emitted when a tenant is successfully provisioned.
    
    Task: 4a9fb493-572e-4e33-bac6-eeb81ba43ec1
    """

    model_config = ConfigDict(populate_by_name=True)

    event_type: str = Field(default="tenant.provisioned", alias="eventType")
    event_id: UUID = Field(alias="eventId")
    timestamp: datetime
    tenant_id: UUID = Field(alias="tenantId")
    tenant_slug: str = Field(alias="tenantSlug")
    tenant_name: str = Field(alias="tenantName")
    created_by: str = Field(alias="createdBy")
    configuration_version: int = Field(alias="configurationVersion")
    metadata: dict[str, str] = Field(default_factory=dict)
