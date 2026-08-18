"""Proficiency CRUD controller with tenant + taxonomy version handling."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status

from asiwdp_skills_framework.deps import TenantContext
from asiwdp_skills_framework.models import Proficiency
from asiwdp_skills_framework.repositories import AuditRepository, ProficiencyRepository
from asiwdp_skills_framework.schemas.requests import (
    ProficiencyCreate,
    ProficiencyUpdate,
)
from asiwdp_skills_framework.schemas.responses import (
    PaginatedProficiencies,
    ProficiencyResponse,
)
from asiwdp_skills_framework.validation import assert_valid_schema


class ProficiencyController:
    def __init__(self, repo: ProficiencyRepository, audit: AuditRepository) -> None:
        self._repo = repo
        self._audit = audit

    def create(self, ctx: TenantContext, body: ProficiencyCreate) -> ProficiencyResponse:
        assert_valid_schema(body.model_dump(mode="json"), "proficiency_create")
        if body.tenant_id and body.tenant_id != ctx.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "tenant_mismatch", "message": "Cross-tenant write denied"},
            )
        version = body.version or ctx.version
        proficiency = Proficiency(
            tenant_id=ctx.tenant_id,
            version=version,
            level=body.level,
            code=body.code,
            name=body.name,
            description=body.description,
            rank_order=body.rank_order,
        )
        try:
            created = self._repo.create(proficiency)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "conflict", "message": str(exc)},
            ) from exc
        self._audit.write(
            tenant_id=ctx.tenant_id,
            version=created.version,
            entity_type="proficiency",
            entity_id=created.id,
            action="CREATE",
            actor_id=ctx.actor_id,
            change_blob=created.model_dump(mode="json"),
        )
        return ProficiencyResponse.model_validate(created)

    def get(self, ctx: TenantContext, proficiency_id: UUID) -> ProficiencyResponse:
        proficiency = self._repo.get(
            tenant_id=ctx.tenant_id, proficiency_id=proficiency_id
        )
        if proficiency is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "not_found", "message": "Proficiency not found"},
            )
        return ProficiencyResponse.model_validate(proficiency)

    def update(
        self, ctx: TenantContext, proficiency_id: UUID, body: ProficiencyUpdate
    ) -> ProficiencyResponse:
        proficiency = self._repo.get(
            tenant_id=ctx.tenant_id, proficiency_id=proficiency_id
        )
        if proficiency is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "not_found", "message": "Proficiency not found"},
            )
        data = body.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(proficiency, key, value)
        updated = self._repo.update(proficiency)
        self._audit.write(
            tenant_id=ctx.tenant_id,
            version=updated.version,
            entity_type="proficiency",
            entity_id=updated.id,
            action="UPDATE",
            actor_id=ctx.actor_id,
            change_blob=data,
        )
        return ProficiencyResponse.model_validate(updated)

    def retire(self, ctx: TenantContext, proficiency_id: UUID) -> ProficiencyResponse:
        proficiency = self._repo.get(
            tenant_id=ctx.tenant_id, proficiency_id=proficiency_id
        )
        if proficiency is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "not_found", "message": "Proficiency not found"},
            )
        proficiency.status = "deprecated"
        updated = self._repo.update(proficiency)
        self._audit.write(
            tenant_id=ctx.tenant_id,
            version=updated.version,
            entity_type="proficiency",
            entity_id=updated.id,
            action="RETIRE",
            actor_id=ctx.actor_id,
            change_blob={"status": "deprecated"},
        )
        return ProficiencyResponse.model_validate(updated)

    def list(
        self,
        ctx: TenantContext,
        *,
        version: int | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedProficiencies:
        items, total = self._repo.list(
            tenant_id=ctx.tenant_id,
            version=version if version is not None else ctx.version,
            status=status,
            limit=limit,
            offset=offset,
        )
        return PaginatedProficiencies(
            items=[ProficiencyResponse.model_validate(i) for i in items],
            total=total,
            limit=limit,
            offset=offset,
        )

    def search(
        self,
        ctx: TenantContext,
        *,
        q: str,
        version: int | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedProficiencies:
        items, total = self._repo.list(
            tenant_id=ctx.tenant_id,
            version=version if version is not None else ctx.version,
            status=status,
            q=q,
            limit=limit,
            offset=offset,
        )
        return PaginatedProficiencies(
            items=[ProficiencyResponse.model_validate(i) for i in items],
            total=total,
            limit=limit,
            offset=offset,
        )
