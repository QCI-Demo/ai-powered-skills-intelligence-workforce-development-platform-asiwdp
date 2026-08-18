"""Outbound response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class SkillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    version: int
    code: str
    name: str
    description: str | None = None
    category: str | None = None
    parent_skill_id: UUID | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    version: int
    code: str
    name: str
    description: str | None = None
    parent_category_id: UUID | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class ProficiencyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    version: int
    level: int
    code: str
    name: str
    description: str | None = None
    rank_order: int
    status: str
    created_at: datetime
    updated_at: datetime


class Paginated(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class PaginatedSkills(BaseModel):
    items: list[SkillResponse]
    total: int
    limit: int
    offset: int


class PaginatedCategories(BaseModel):
    items: list[CategoryResponse]
    total: int
    limit: int
    offset: int


class PaginatedProficiencies(BaseModel):
    items: list[ProficiencyResponse]
    total: int
    limit: int
    offset: int


class ImportRowError(BaseModel):
    row_number: int
    entity_type: str | None = None
    code: str | None = None
    errors: list[str] = Field(default_factory=list)
    raw: dict[str, Any] | None = None


class ImportReport(BaseModel):
    import_id: UUID
    tenant_id: UUID
    version: int
    format: str
    entity_type: str
    total_rows: int
    success_count: int
    error_count: int
    skipped_count: int = 0
    errors: list[ImportRowError] = Field(default_factory=list)
    created_ids: list[UUID] = Field(default_factory=list)
    audit_entries: int = 0
