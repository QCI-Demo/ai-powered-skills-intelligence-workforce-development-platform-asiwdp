"""Domain models for versioned skills taxonomy entities."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

EntityStatus = Literal["active", "deprecated", "draft"]
EntityType = Literal["skill", "category", "proficiency"]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Skill(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    version: int = Field(ge=1, default=1)
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    category: str | None = Field(default=None, max_length=128)
    parent_skill_id: UUID | None = None
    status: EntityStatus = "active"
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()


class Category(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    version: int = Field(ge=1, default=1)
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    parent_category_id: UUID | None = None
    status: EntityStatus = "active"
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()


class Proficiency(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    version: int = Field(ge=1, default=1)
    level: int = Field(ge=1)
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    rank_order: int
    status: EntityStatus = "active"
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()


class AuditEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    version: int = Field(ge=1, default=1)
    entity_type: str
    entity_id: UUID
    action: str
    actor_id: UUID | None = None
    correlation_id: UUID | None = None
    change_blob: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)
    row_number: int | None = None
