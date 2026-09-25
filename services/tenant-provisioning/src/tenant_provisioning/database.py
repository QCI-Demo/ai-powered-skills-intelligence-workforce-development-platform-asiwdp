"""SQLAlchemy database models and repository.

Task: 89d8dbba-19a6-4a35-8382-d1be49c1fcf0
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, relationship

from tenant_provisioning.models import (
    CreateTenantRequest,
    TenantConfiguration,
    TenantResponse,
)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""

    pass


class TenantEntity(Base):
    """Tenant database entity."""

    __tablename__ = "tenants"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(128), nullable=False, unique=True)
    status = Column(String(32), nullable=False, default="provisioning")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_by = Column(String(255), nullable=False)

    configuration = relationship(
        "TenantConfigurationEntity",
        back_populates="tenant",
        uselist=False,
        cascade="all, delete-orphan",
    )
    metadata_entries = relationship(
        "TenantMetadataEntity",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )


class TenantConfigurationEntity(Base):
    """Tenant configuration database entity."""

    __tablename__ = "tenant_configurations"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    feature_flags = Column(JSONB, nullable=False, default=dict)
    limits = Column(JSONB, nullable=False, default=dict)
    branding = Column(JSONB, nullable=False, default=dict)
    integrations = Column(JSONB, nullable=False, default=dict)
    config_version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    tenant = relationship("TenantEntity", back_populates="configuration")


class TenantMetadataEntity(Base):
    """Tenant metadata database entity."""

    __tablename__ = "tenant_metadata"
    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_tenant_metadata_key"),)

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    key = Column(String(255), nullable=False)
    value = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    tenant = relationship("TenantEntity", back_populates="metadata_entries")


class IdempotencyKeyEntity(Base):
    """Idempotency key database entity.
    
    Task: 78cab998-3bb5-4262-bc80-e2160bdc2805
    """

    __tablename__ = "idempotency_keys"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    idempotency_key = Column(String(255), nullable=False, unique=True)
    tenant_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
    )
    request_hash = Column(String(64), nullable=False)
    response = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=False)


class TenantRepository:
    """Repository for tenant database operations.
    
    Task: 78cab998-3bb5-4262-bc80-e2160bdc2805
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _compute_request_hash(request: CreateTenantRequest) -> str:
        """Compute SHA-256 hash of request body for idempotency conflict detection."""
        data = request.model_dump_json(by_alias=True)
        return hashlib.sha256(data.encode()).hexdigest()

    async def check_idempotency_key(
        self,
        idempotency_key: str,
        request: CreateTenantRequest,
    ) -> tuple[bool, dict[str, Any] | None]:
        """Check if idempotency key exists and matches request.
        
        Returns:
            (exists, response) - If exists and matches, returns cached response.
            Raises ValueError if key exists but request hash doesn't match.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(IdempotencyKeyEntity).where(
                    IdempotencyKeyEntity.idempotency_key == idempotency_key
                )
            )
            existing = result.scalar_one_or_none()

            if existing is None:
                return False, None

            request_hash = self._compute_request_hash(request)
            if existing.request_hash != request_hash:
                raise ValueError(
                    "Idempotency key already used with different request body"
                )

            return True, existing.response

    async def create_tenant(
        self,
        request: CreateTenantRequest,
        created_by: str,
        idempotency_key: str | None = None,
        idempotency_ttl_hours: int = 24,
    ) -> TenantResponse:
        """Create a new tenant with configuration atomically.
        
        Task: 78cab998-3bb5-4262-bc80-e2160bdc2805
        Persist tenant and default configuration atomically.
        """
        config = request.configuration or TenantConfiguration.default()
        tenant_id = uuid4()
        now = datetime.now(timezone.utc)

        async with self._session_factory() as session:
            async with session.begin():
                # Check for slug uniqueness
                slug_check = await session.execute(
                    select(TenantEntity).where(TenantEntity.slug == request.slug)
                )
                if slug_check.scalar_one_or_none() is not None:
                    raise ValueError(f"Tenant with slug '{request.slug}' already exists")

                # Create tenant entity
                tenant = TenantEntity(
                    id=tenant_id,
                    name=request.name,
                    slug=request.slug,
                    status="active",
                    created_at=now,
                    updated_at=now,
                    created_by=created_by,
                )
                session.add(tenant)

                # Create configuration entity
                config_entity = TenantConfigurationEntity(
                    tenant_id=tenant_id,
                    feature_flags=config.feature_flags.model_dump(by_alias=True),
                    limits=config.limits.model_dump(by_alias=True),
                    branding=config.branding.model_dump(by_alias=True),
                    integrations=config.integrations.model_dump(by_alias=True),
                    config_version=config.version,
                    created_at=now,
                    updated_at=now,
                )
                session.add(config_entity)

                # Create metadata entries
                for key, value in request.metadata.items():
                    metadata_entity = TenantMetadataEntity(
                        tenant_id=tenant_id,
                        key=key,
                        value=value,
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(metadata_entity)

                # Build response
                response = TenantResponse(
                    id=tenant_id,
                    name=request.name,
                    slug=request.slug,
                    status="active",
                    configuration=config,
                    metadata=request.metadata,
                    createdAt=now,
                    updatedAt=now,
                    createdBy=created_by,
                )

                # Store idempotency key if provided
                if idempotency_key:
                    idempotency_entity = IdempotencyKeyEntity(
                        idempotency_key=idempotency_key,
                        tenant_id=tenant_id,
                        request_hash=self._compute_request_hash(request),
                        response=json.loads(response.model_dump_json(by_alias=True)),
                        created_at=now,
                        expires_at=now + timedelta(hours=idempotency_ttl_hours),
                    )
                    session.add(idempotency_entity)

        return response

    async def get_tenant_by_id(self, tenant_id: UUID) -> TenantResponse | None:
        """Get tenant by ID."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(TenantEntity).where(TenantEntity.id == tenant_id)
            )
            tenant = result.scalar_one_or_none()
            if tenant is None:
                return None

            return self._entity_to_response(tenant)

    async def get_tenant_by_slug(self, slug: str) -> TenantResponse | None:
        """Get tenant by slug."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(TenantEntity).where(TenantEntity.slug == slug)
            )
            tenant = result.scalar_one_or_none()
            if tenant is None:
                return None

            return self._entity_to_response(tenant)

    def _entity_to_response(self, tenant: TenantEntity) -> TenantResponse:
        """Convert tenant entity to response model."""
        config = TenantConfiguration(
            feature_flags=tenant.configuration.feature_flags,
            limits=tenant.configuration.limits,
            branding=tenant.configuration.branding,
            integrations=tenant.configuration.integrations,
            version=tenant.configuration.config_version,
        )
        metadata = {m.key: m.value for m in tenant.metadata_entries}

        return TenantResponse(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            status=tenant.status,
            configuration=config,
            metadata=metadata,
            createdAt=tenant.created_at,
            updatedAt=tenant.updated_at,
            createdBy=tenant.created_by,
        )


def create_engine_and_session(database_url: str) -> async_sessionmaker[AsyncSession]:
    """Create async engine and session factory."""
    engine = create_async_engine(database_url, echo=False)
    return async_sessionmaker(engine, expire_on_commit=False)
