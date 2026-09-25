"""Pydantic models for tenant provisioning."""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TenantStatus(str, Enum):
    """Tenant lifecycle status."""

    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEPROVISIONED = "deprovisioned"
    FAILED = "failed"


class PlanTier(str, Enum):
    """Subscription plan tier."""

    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"


class ConfigCategory(str, Enum):
    """Configuration category."""

    GENERAL = "general"
    SECURITY = "security"
    INTEGRATION = "integration"
    FEATURE_FLAGS = "feature_flags"
    BRANDING = "branding"
    NOTIFICATIONS = "notifications"
    COMPLIANCE = "compliance"


class EventStatus(str, Enum):
    """Provisioning event status."""

    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"
    ACKNOWLEDGED = "acknowledged"


# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------


class CreateTenantRequest(BaseModel):
    """Request payload for creating a new tenant."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unique tenant name (slug-like)",
    )
    display_name: str | None = Field(
        None,
        max_length=500,
        description="Human-readable display name",
    )
    domain: str | None = Field(
        None,
        max_length=255,
        description="Custom domain for tenant",
    )
    plan_tier: PlanTier = Field(
        PlanTier.STARTER,
        description="Subscription plan tier",
    )
    settings: dict[str, Any] = Field(
        default_factory=dict,
        description="Initial tenant settings",
    )
    metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Arbitrary key-value metadata",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure name is slug-like."""
        if not re.match(r"^[a-z0-9][a-z0-9\-_]*[a-z0-9]$|^[a-z0-9]$", v.lower()):
            raise ValueError(
                "Name must be slug-like: lowercase alphanumeric with hyphens/underscores"
            )
        return v.lower()

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str | None) -> str | None:
        """Basic domain validation."""
        if v is None:
            return None
        v = v.lower().strip()
        if not re.match(r"^[a-z0-9][a-z0-9\-\.]*[a-z0-9]\.[a-z]{2,}$", v):
            raise ValueError("Invalid domain format")
        return v


# ---------------------------------------------------------------------------
# Response Models
# ---------------------------------------------------------------------------


class TenantConfigurationResponse(BaseModel):
    """Single configuration entry."""

    model_config = ConfigDict(from_attributes=True)

    config_id: UUID
    config_key: str
    config_value: Any
    category: ConfigCategory
    is_active: bool
    version: int


class TenantResponse(BaseModel):
    """Full tenant response."""

    model_config = ConfigDict(from_attributes=True)

    tenant_id: UUID
    name: str
    display_name: str | None
    domain: str | None
    status: TenantStatus
    plan_tier: PlanTier
    settings: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    created_by: str
    provisioned_at: datetime | None = None


class CreateTenantResponse(BaseModel):
    """Response for tenant creation."""

    tenant: TenantResponse
    configurations: list[TenantConfigurationResponse]
    idempotent: bool = Field(
        False,
        description="True if response was cached from idempotency key",
    )


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    message: str
    details: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Event Models
# ---------------------------------------------------------------------------


class TenantProvisioningEvent(BaseModel):
    """Event emitted after tenant provisioning."""

    event_id: UUID
    event_type: str = "tenant.provisioned"
    tenant_id: UUID
    tenant_name: str
    plan_tier: PlanTier
    created_by: str
    timestamp: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_event_payload(self) -> dict[str, Any]:
        """Convert to serializable event payload."""
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "tenant_id": str(self.tenant_id),
            "tenant_name": self.tenant_name,
            "plan_tier": self.plan_tier.value,
            "created_by": self.created_by,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }
