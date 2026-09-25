"""Pydantic models for tenant provisioning API."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class TenantStatus(str, Enum):
    """Tenant lifecycle status."""

    PROVISIONING = "provisioning"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"
    FAILED = "failed"


class TenantTier(str, Enum):
    """Subscription tier determining features and limits."""

    FREE = "free"
    STANDARD = "standard"
    ENTERPRISE = "enterprise"


class CreateTenantRequest(BaseModel):
    """Request payload for creating a new tenant."""

    model_config = ConfigDict(str_strip_whitespace=True, str_min_length=1)

    name: str = Field(..., min_length=1, max_length=255, description="Tenant display name")
    slug: str = Field(
        ...,
        min_length=3,
        max_length=100,
        pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$",
        description="URL-safe unique identifier",
    )
    contact_email: EmailStr = Field(..., description="Primary contact email address")
    billing_email: EmailStr | None = Field(None, description="Billing contact email")
    tier: TenantTier = Field(TenantTier.STANDARD, description="Subscription tier")
    metadata: dict[str, Any] | None = Field(None, description="Custom metadata attributes")

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        """Ensure slug is lowercase and valid format."""
        v = v.lower()
        if "--" in v:
            raise ValueError("Slug cannot contain consecutive hyphens")
        reserved = {"admin", "api", "www", "app", "auth", "system", "platform"}
        if v in reserved:
            raise ValueError(f"Slug '{v}' is reserved")
        return v


class TenantFeatures(BaseModel):
    """Feature flags for tenant."""

    skills_framework: bool = True
    recommendations: bool = True
    learning_paths: bool = True
    analytics: bool = True


class TenantLimits(BaseModel):
    """Usage limits for tenant."""

    max_users: int = 100
    max_organizations: int = 10
    api_rate_limit: int = 1000  # requests per minute


class TenantRetention(BaseModel):
    """Data retention settings."""

    audit_logs_days: int = 365
    analytics_days: int = 730


class TenantPrivacy(BaseModel):
    """Privacy and compliance settings."""

    data_region: str = "us-east-1"
    gdpr_enabled: bool = True


class TenantBranding(BaseModel):
    """Branding customization."""

    logo_url: str | None = None
    primary_color: str = "#1a73e8"


class TenantNotifications(BaseModel):
    """Notification settings."""

    email_enabled: bool = True
    webhook_url: str | None = None


class TenantConfiguration(BaseModel):
    """Complete tenant configuration."""

    features: TenantFeatures = Field(default_factory=TenantFeatures)
    limits: TenantLimits = Field(default_factory=TenantLimits)
    retention: TenantRetention = Field(default_factory=TenantRetention)
    privacy: TenantPrivacy = Field(default_factory=TenantPrivacy)
    branding: TenantBranding = Field(default_factory=TenantBranding)
    notifications: TenantNotifications = Field(default_factory=TenantNotifications)

    @classmethod
    def for_tier(cls, tier: TenantTier) -> TenantConfiguration:
        """Create configuration with tier-specific defaults."""
        config = cls()
        if tier == TenantTier.FREE:
            config.limits.max_users = 10
            config.limits.max_organizations = 1
            config.limits.api_rate_limit = 100
            config.features.analytics = False
        elif tier == TenantTier.ENTERPRISE:
            config.limits.max_users = -1  # unlimited
            config.limits.max_organizations = -1  # unlimited
            config.limits.api_rate_limit = 10000
            config.retention.audit_logs_days = 730
            config.retention.analytics_days = 2555  # 7 years
        return config


class TenantResponse(BaseModel):
    """Response model for tenant operations."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    status: TenantStatus
    tier: TenantTier
    contact_email: str
    billing_email: str | None
    metadata: dict[str, Any] | None
    configuration: TenantConfiguration
    created_at: datetime
    updated_at: datetime
    provisioned_at: datetime | None
    created_by: UUID


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    message: str
    details: dict[str, Any] | None = None
