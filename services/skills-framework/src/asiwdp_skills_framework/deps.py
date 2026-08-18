"""FastAPI dependencies: tenant context, version header, repositories."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status

from asiwdp_skills_framework.repositories import (
    AuditRepository,
    CategoryRepository,
    ProficiencyRepository,
    SkillRepository,
)
from asiwdp_skills_framework.services.bulk_import import BulkImportValidationService
from asiwdp_skills_framework.services.taxonomy_export import TaxonomyExportService
from asiwdp_skills_framework.store import TaxonomyStore

TAXONOMY_VERSION_HEADER = "X-Taxonomy-Version"


@dataclass(frozen=True, slots=True)
class TenantContext:
    tenant_id: UUID
    actor_id: UUID | None
    version: int
    principal: object | None = None


def get_store(request: Request) -> TaxonomyStore:
    store = getattr(request.app.state, "taxonomy_store", None)
    if store is None:
        raise RuntimeError("Taxonomy store is not configured on the application")
    return store


def get_skill_repo(store: Annotated[TaxonomyStore, Depends(get_store)]) -> SkillRepository:
    return SkillRepository(store)


def get_category_repo(
    store: Annotated[TaxonomyStore, Depends(get_store)],
) -> CategoryRepository:
    return CategoryRepository(store)


def get_proficiency_repo(
    store: Annotated[TaxonomyStore, Depends(get_store)],
) -> ProficiencyRepository:
    return ProficiencyRepository(store)


def get_audit_repo(
    store: Annotated[TaxonomyStore, Depends(get_store)],
) -> AuditRepository:
    return AuditRepository(store)


def get_import_service(
    skills: Annotated[SkillRepository, Depends(get_skill_repo)],
    categories: Annotated[CategoryRepository, Depends(get_category_repo)],
    proficiencies: Annotated[ProficiencyRepository, Depends(get_proficiency_repo)],
    audit: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> BulkImportValidationService:
    return BulkImportValidationService(
        skills=skills,
        categories=categories,
        proficiencies=proficiencies,
        audit=audit,
    )


def get_export_service(
    skills: Annotated[SkillRepository, Depends(get_skill_repo)],
    categories: Annotated[CategoryRepository, Depends(get_category_repo)],
    proficiencies: Annotated[ProficiencyRepository, Depends(get_proficiency_repo)],
) -> TaxonomyExportService:
    return TaxonomyExportService(
        skills=skills,
        categories=categories,
        proficiencies=proficiencies,
    )


def _principal_from_request(request: Request) -> object | None:
    return getattr(request.state, "principal", None)


def get_tenant_context(
    request: Request,
    x_taxonomy_version: Annotated[
        int | None, Header(alias=TAXONOMY_VERSION_HEADER)
    ] = None,
    x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-Id")] = None,
) -> TenantContext:
    """
    Resolve tenant isolation + taxonomy version.

    Prefer JWT principal.tenant_id when auth middleware is mounted; fall back to
    X-Tenant-Id for local/dev test harnesses.
    """
    principal = _principal_from_request(request)
    tenant_raw: str | None = None
    actor_id: UUID | None = None

    if principal is not None:
        tenant_raw = getattr(principal, "tenant_id", None)
        subject = getattr(principal, "subject", None)
        if subject:
            try:
                actor_id = UUID(str(subject))
            except ValueError:
                actor_id = None

    if not tenant_raw:
        tenant_raw = x_tenant_id

    if not tenant_raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "tenant_required",
                "message": "Tenant context missing from token or X-Tenant-Id header",
            },
        )

    try:
        tenant_id = UUID(str(tenant_raw))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_tenant", "message": "tenant_id is not a UUID"},
        ) from exc

    version = x_taxonomy_version if x_taxonomy_version is not None else 1
    if version < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_version",
                "message": f"{TAXONOMY_VERSION_HEADER} must be >= 1",
            },
        )

    return TenantContext(
        tenant_id=tenant_id,
        actor_id=actor_id,
        version=version,
        principal=principal,
    )
