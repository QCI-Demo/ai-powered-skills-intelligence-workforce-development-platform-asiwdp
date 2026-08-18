"""Skill CRUD controller with tenant + taxonomy version handling."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status

from asiwdp_skills_framework.deps import TenantContext
from asiwdp_skills_framework.models import Skill
from asiwdp_skills_framework.repositories import AuditRepository, SkillRepository
from asiwdp_skills_framework.schemas.requests import SkillCreate, SkillUpdate
from asiwdp_skills_framework.schemas.responses import PaginatedSkills, SkillResponse
from asiwdp_skills_framework.validation import assert_valid_schema


class SkillController:
    def __init__(self, repo: SkillRepository, audit: AuditRepository) -> None:
        self._repo = repo
        self._audit = audit

    def create(self, ctx: TenantContext, body: SkillCreate) -> SkillResponse:
        assert_valid_schema(body.model_dump(mode="json"), "skill_create")
        if body.tenant_id and body.tenant_id != ctx.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "tenant_mismatch", "message": "Cross-tenant write denied"},
            )
        version = body.version or ctx.version
        skill = Skill(
            tenant_id=ctx.tenant_id,
            version=version,
            code=body.code,
            name=body.name,
            description=body.description,
            category=body.category,
            parent_skill_id=body.parent_skill_id,
        )
        try:
            created = self._repo.create(skill)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "conflict", "message": str(exc)},
            ) from exc
        self._audit.write(
            tenant_id=ctx.tenant_id,
            version=created.version,
            entity_type="skill",
            entity_id=created.id,
            action="CREATE",
            actor_id=ctx.actor_id,
            change_blob=created.model_dump(mode="json"),
        )
        return SkillResponse.model_validate(created)

    def get(self, ctx: TenantContext, skill_id: UUID) -> SkillResponse:
        skill = self._repo.get(tenant_id=ctx.tenant_id, skill_id=skill_id)
        if skill is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "not_found", "message": "Skill not found"},
            )
        return SkillResponse.model_validate(skill)

    def update(
        self, ctx: TenantContext, skill_id: UUID, body: SkillUpdate
    ) -> SkillResponse:
        skill = self._repo.get(tenant_id=ctx.tenant_id, skill_id=skill_id)
        if skill is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "not_found", "message": "Skill not found"},
            )
        data = body.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(skill, key, value)
        updated = self._repo.update(skill)
        self._audit.write(
            tenant_id=ctx.tenant_id,
            version=updated.version,
            entity_type="skill",
            entity_id=updated.id,
            action="UPDATE",
            actor_id=ctx.actor_id,
            change_blob=data,
        )
        return SkillResponse.model_validate(updated)

    def retire(self, ctx: TenantContext, skill_id: UUID) -> SkillResponse:
        skill = self._repo.get(tenant_id=ctx.tenant_id, skill_id=skill_id)
        if skill is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "not_found", "message": "Skill not found"},
            )
        skill.status = "deprecated"
        updated = self._repo.update(skill)
        self._audit.write(
            tenant_id=ctx.tenant_id,
            version=updated.version,
            entity_type="skill",
            entity_id=updated.id,
            action="RETIRE",
            actor_id=ctx.actor_id,
            change_blob={"status": "deprecated"},
        )
        return SkillResponse.model_validate(updated)

    def list(
        self,
        ctx: TenantContext,
        *,
        version: int | None = None,
        status: str | None = None,
        category: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedSkills:
        items, total = self._repo.list(
            tenant_id=ctx.tenant_id,
            version=version if version is not None else ctx.version,
            status=status,
            category=category,
            limit=limit,
            offset=offset,
        )
        return PaginatedSkills(
            items=[SkillResponse.model_validate(i) for i in items],
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
    ) -> PaginatedSkills:
        items, total = self._repo.list(
            tenant_id=ctx.tenant_id,
            version=version if version is not None else ctx.version,
            status=status,
            q=q,
            limit=limit,
            offset=offset,
        )
        return PaginatedSkills(
            items=[SkillResponse.model_validate(i) for i in items],
            total=total,
            limit=limit,
            offset=offset,
        )
