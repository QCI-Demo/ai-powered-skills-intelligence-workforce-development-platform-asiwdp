"""SQLAlchemy ORM entities for tenant provisioning."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from tenant_provisioning.models import (
    ConfigCategory,
    EventStatus,
    PlanTier,
    TenantStatus,
)


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    type_annotation_map = {
        dict[str, Any]: JSONB,
    }


class Tenant(Base):
    """Tenant entity."""

    __tablename__ = "tenants"

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    display_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, name="tenant_status"),
        nullable=False,
        default=TenantStatus.PENDING,
    )
    plan_tier: Mapped[PlanTier] = mapped_column(
        Enum(PlanTier, name="plan_tier"),
        nullable=False,
        default=PlanTier.STARTER,
    )
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    provisioned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deprovisioned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    configurations: Mapped[list["TenantConfiguration"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
    metadata_entries: Mapped[list["TenantMetadata"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
    provisioning_events: Mapped[list["ProvisioningEvent"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list["TenantAuditLog"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_tenants_status", "status"),
        Index("idx_tenants_plan_tier", "plan_tier"),
        Index("idx_tenants_created_at", "created_at"),
    )


class TenantConfiguration(Base):
    """Tenant configuration key-value store."""

    __tablename__ = "tenant_configurations"

    config_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    )
    config_key: Mapped[str] = mapped_column(String(255), nullable=False)
    config_value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    category: Mapped[ConfigCategory] = mapped_column(
        Enum(ConfigCategory, name="config_category"),
        nullable=False,
        default=ConfigCategory.GENERAL,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationship
    tenant: Mapped["Tenant"] = relationship(back_populates="configurations")

    __table_args__ = (
        UniqueConstraint("tenant_id", "config_key", name="uq_tenant_config_key"),
        Index("idx_tenant_configs_tenant_id", "tenant_id"),
        Index("idx_tenant_configs_category", "tenant_id", "category"),
    )


class TenantMetadata(Base):
    """Arbitrary tenant metadata."""

    __tablename__ = "tenant_metadata"

    metadata_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    )
    metadata_key: Mapped[str] = mapped_column(String(255), nullable=False)
    metadata_value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationship
    tenant: Mapped["Tenant"] = relationship(back_populates="metadata_entries")

    __table_args__ = (
        UniqueConstraint("tenant_id", "metadata_key", name="uq_tenant_metadata_key"),
        Index("idx_tenant_metadata_tenant_id", "tenant_id"),
    )


class IdempotencyKey(Base):
    """Idempotency key store for safe request replay."""

    __tablename__ = "idempotency_keys"

    idempotency_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    tenant_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_body: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("idx_idempotency_expires", "expires_at"),)


class ProvisioningEvent(Base):
    """Provisioning events for downstream processing."""

    __tablename__ = "provisioning_events"

    event_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    event_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[EventStatus] = mapped_column(
        Enum(EventStatus, name="event_status"),
        nullable=False,
        default=EventStatus.PENDING,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationship
    tenant: Mapped["Tenant"] = relationship(back_populates="provisioning_events")

    __table_args__ = (
        Index("idx_prov_events_tenant_type", "tenant_id", "event_type"),
        Index("idx_prov_events_created_at", "created_at"),
    )


class TenantAuditLog(Base):
    """Audit log for compliance."""

    __tablename__ = "tenant_audit_logs"

    audit_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(50), nullable=False, default="user")
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    changes: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationship
    tenant: Mapped["Tenant"] = relationship(back_populates="audit_logs")

    __table_args__ = (
        Index("idx_audit_tenant_created", "tenant_id", "created_at"),
        Index("idx_audit_actor", "actor_id"),
    )
