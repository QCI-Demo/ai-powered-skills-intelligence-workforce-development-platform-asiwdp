"""Inbound request body schemas (validated via Pydantic + JSON Schema)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SkillCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    category: str | None = Field(default=None, max_length=128)
    parent_skill_id: UUID | None = None
    version: int | None = Field(default=None, ge=1)
    tenant_id: UUID | None = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()


class SkillUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    category: str | None = Field(default=None, max_length=128)
    parent_skill_id: UUID | None = None
    status: str | None = Field(default=None, pattern="^(active|deprecated|draft)$")


class CategoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    parent_category_id: UUID | None = None
    version: int | None = Field(default=None, ge=1)
    tenant_id: UUID | None = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()


class CategoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    parent_category_id: UUID | None = None
    status: str | None = Field(default=None, pattern="^(active|deprecated|draft)$")


class ProficiencyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: int = Field(ge=1)
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    rank_order: int
    version: int | None = Field(default=None, ge=1)
    tenant_id: UUID | None = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()


class ProficiencyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: int | None = Field(default=None, ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    rank_order: int | None = None
    status: str | None = Field(default=None, pattern="^(active|deprecated|draft)$")
