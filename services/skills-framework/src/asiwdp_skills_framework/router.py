"""API route definitions for skills, categories, proficiency, import, export."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse

from asiwdp_skills_framework.controllers.category_controller import CategoryController
from asiwdp_skills_framework.controllers.proficiency_controller import (
    ProficiencyController,
)
from asiwdp_skills_framework.controllers.skill_controller import SkillController
from asiwdp_skills_framework.deps import (
    TenantContext,
    get_audit_repo,
    get_category_repo,
    get_export_service,
    get_import_service,
    get_proficiency_repo,
    get_skill_repo,
    get_tenant_context,
)
from asiwdp_skills_framework.repositories import (
    AuditRepository,
    CategoryRepository,
    ProficiencyRepository,
    SkillRepository,
)
from asiwdp_skills_framework.schemas.requests import (
    CategoryCreate,
    CategoryUpdate,
    ProficiencyCreate,
    ProficiencyUpdate,
    SkillCreate,
    SkillUpdate,
)
from asiwdp_skills_framework.schemas.responses import (
    CategoryResponse,
    ImportReport,
    PaginatedCategories,
    PaginatedProficiencies,
    PaginatedSkills,
    ProficiencyResponse,
    SkillResponse,
)
from asiwdp_skills_framework.services.bulk_import import BulkImportValidationService
from asiwdp_skills_framework.services.taxonomy_export import TaxonomyExportService

api_router = APIRouter()


def _skill_controller(
    repo: Annotated[SkillRepository, Depends(get_skill_repo)],
    audit: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> SkillController:
    return SkillController(repo, audit)


def _category_controller(
    repo: Annotated[CategoryRepository, Depends(get_category_repo)],
    audit: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> CategoryController:
    return CategoryController(repo, audit)


def _proficiency_controller(
    repo: Annotated[ProficiencyRepository, Depends(get_proficiency_repo)],
    audit: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> ProficiencyController:
    return ProficiencyController(repo, audit)


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------
@api_router.post(
    "/skills",
    response_model=SkillResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Skills"],
)
def create_skill(
    body: SkillCreate,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    controller: Annotated[SkillController, Depends(_skill_controller)],
) -> SkillResponse:
    return controller.create(ctx, body)


@api_router.get("/skills", response_model=PaginatedSkills, tags=["Skills"])
def list_skills(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    controller: Annotated[SkillController, Depends(_skill_controller)],
    version: int | None = Query(default=None, ge=1),
    status_filter: str | None = Query(default=None, alias="status"),
    category: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PaginatedSkills:
    return controller.list(
        ctx,
        version=version,
        status=status_filter,
        category=category,
        limit=limit,
        offset=offset,
    )


@api_router.get("/skills/search", response_model=PaginatedSkills, tags=["Skills"])
def search_skills(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    controller: Annotated[SkillController, Depends(_skill_controller)],
    q: str = Query(min_length=1),
    version: int | None = Query(default=None, ge=1),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PaginatedSkills:
    return controller.search(
        ctx, q=q, version=version, status=status_filter, limit=limit, offset=offset
    )


@api_router.get("/skills/{skill_id}", response_model=SkillResponse, tags=["Skills"])
def get_skill(
    skill_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    controller: Annotated[SkillController, Depends(_skill_controller)],
) -> SkillResponse:
    return controller.get(ctx, skill_id)


@api_router.patch("/skills/{skill_id}", response_model=SkillResponse, tags=["Skills"])
def update_skill(
    skill_id: UUID,
    body: SkillUpdate,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    controller: Annotated[SkillController, Depends(_skill_controller)],
) -> SkillResponse:
    return controller.update(ctx, skill_id, body)


@api_router.post(
    "/skills/{skill_id}/retire", response_model=SkillResponse, tags=["Skills"]
)
def retire_skill(
    skill_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    controller: Annotated[SkillController, Depends(_skill_controller)],
) -> SkillResponse:
    return controller.retire(ctx, skill_id)


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------
@api_router.post(
    "/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Categories"],
)
def create_category(
    body: CategoryCreate,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    controller: Annotated[CategoryController, Depends(_category_controller)],
) -> CategoryResponse:
    return controller.create(ctx, body)


@api_router.get(
    "/categories", response_model=PaginatedCategories, tags=["Categories"]
)
def list_categories(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    controller: Annotated[CategoryController, Depends(_category_controller)],
    version: int | None = Query(default=None, ge=1),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PaginatedCategories:
    return controller.list(
        ctx, version=version, status=status_filter, limit=limit, offset=offset
    )


@api_router.get(
    "/categories/search", response_model=PaginatedCategories, tags=["Categories"]
)
def search_categories(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    controller: Annotated[CategoryController, Depends(_category_controller)],
    q: str = Query(min_length=1),
    version: int | None = Query(default=None, ge=1),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PaginatedCategories:
    return controller.search(
        ctx, q=q, version=version, status=status_filter, limit=limit, offset=offset
    )


@api_router.get(
    "/categories/{category_id}", response_model=CategoryResponse, tags=["Categories"]
)
def get_category(
    category_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    controller: Annotated[CategoryController, Depends(_category_controller)],
) -> CategoryResponse:
    return controller.get(ctx, category_id)


@api_router.patch(
    "/categories/{category_id}", response_model=CategoryResponse, tags=["Categories"]
)
def update_category(
    category_id: UUID,
    body: CategoryUpdate,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    controller: Annotated[CategoryController, Depends(_category_controller)],
) -> CategoryResponse:
    return controller.update(ctx, category_id, body)


@api_router.post(
    "/categories/{category_id}/retire",
    response_model=CategoryResponse,
    tags=["Categories"],
)
def retire_category(
    category_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    controller: Annotated[CategoryController, Depends(_category_controller)],
) -> CategoryResponse:
    return controller.retire(ctx, category_id)


# ---------------------------------------------------------------------------
# Proficiencies
# ---------------------------------------------------------------------------
@api_router.post(
    "/proficiencies",
    response_model=ProficiencyResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Proficiencies"],
)
def create_proficiency(
    body: ProficiencyCreate,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    controller: Annotated[ProficiencyController, Depends(_proficiency_controller)],
) -> ProficiencyResponse:
    return controller.create(ctx, body)


@api_router.get(
    "/proficiencies", response_model=PaginatedProficiencies, tags=["Proficiencies"]
)
def list_proficiencies(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    controller: Annotated[ProficiencyController, Depends(_proficiency_controller)],
    version: int | None = Query(default=None, ge=1),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PaginatedProficiencies:
    return controller.list(
        ctx, version=version, status=status_filter, limit=limit, offset=offset
    )


@api_router.get(
    "/proficiencies/search",
    response_model=PaginatedProficiencies,
    tags=["Proficiencies"],
)
def search_proficiencies(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    controller: Annotated[ProficiencyController, Depends(_proficiency_controller)],
    q: str = Query(min_length=1),
    version: int | None = Query(default=None, ge=1),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PaginatedProficiencies:
    return controller.search(
        ctx, q=q, version=version, status=status_filter, limit=limit, offset=offset
    )


@api_router.get(
    "/proficiencies/{proficiency_id}",
    response_model=ProficiencyResponse,
    tags=["Proficiencies"],
)
def get_proficiency(
    proficiency_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    controller: Annotated[ProficiencyController, Depends(_proficiency_controller)],
) -> ProficiencyResponse:
    return controller.get(ctx, proficiency_id)


@api_router.patch(
    "/proficiencies/{proficiency_id}",
    response_model=ProficiencyResponse,
    tags=["Proficiencies"],
)
def update_proficiency(
    proficiency_id: UUID,
    body: ProficiencyUpdate,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    controller: Annotated[ProficiencyController, Depends(_proficiency_controller)],
) -> ProficiencyResponse:
    return controller.update(ctx, proficiency_id, body)


@api_router.post(
    "/proficiencies/{proficiency_id}/retire",
    response_model=ProficiencyResponse,
    tags=["Proficiencies"],
)
def retire_proficiency(
    proficiency_id: UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    controller: Annotated[ProficiencyController, Depends(_proficiency_controller)],
) -> ProficiencyResponse:
    return controller.retire(ctx, proficiency_id)


# ---------------------------------------------------------------------------
# Bulk import
# ---------------------------------------------------------------------------
@api_router.post(
    "/taxonomy/import",
    response_model=ImportReport,
    tags=["Taxonomy"],
)
async def import_taxonomy(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    service: Annotated[BulkImportValidationService, Depends(get_import_service)],
    file: UploadFile = File(...),
    entity_type: Literal["skill", "category", "proficiency"] = Form(...),
    format: Literal["csv", "json", "ndjson"] = Form(default="csv"),
    version: int | None = Form(default=None),
) -> ImportReport:
    import_version = version if version is not None else ctx.version
    try:
        report = service.import_stream(
            file.file,
            tenant_id=ctx.tenant_id,
            version=import_version,
            entity_type=entity_type,
            format=format,
            actor_id=ctx.actor_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "import_error", "message": str(exc)},
        ) from exc
    return report


# ---------------------------------------------------------------------------
# Taxonomy export
# ---------------------------------------------------------------------------
@api_router.get("/taxonomy/export", tags=["Taxonomy"])
def export_taxonomy(
    request: Request,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    service: Annotated[TaxonomyExportService, Depends(get_export_service)],
    tenant_id: UUID | None = Query(
        default=None,
        description="Optional explicit tenant filter; must match caller tenant",
    ),
    version: int | None = Query(
        default=None,
        ge=1,
        description="Taxonomy version; omit for header version / current snapshot",
    ),
    format: str | None = Query(default=None, description="Override Accept negotiation"),
    accept: Annotated[str | None, Header(alias="Accept")] = None,
) -> StreamingResponse:
    export_tenant = tenant_id or ctx.tenant_id
    if export_tenant != ctx.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "tenant_mismatch",
                "message": "tenant_id query must match authenticated tenant",
            },
        )
    export_version = version if version is not None else ctx.version
    try:
        resolved = service.resolve_format(accept=accept, format_query=format)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail={"error": "not_acceptable", "message": str(exc)},
        ) from exc

    if resolved == "csv":
        media_type = "text/csv"
        filename = f"taxonomy-{export_tenant}-v{export_version}.csv"
        generator = service.stream_csv(
            tenant_id=export_tenant, version=export_version
        )
    else:
        media_type = "application/json"
        filename = f"taxonomy-{export_tenant}-v{export_version}.json"
        generator = service.stream_json(
            tenant_id=export_tenant, version=export_version
        )

    return StreamingResponse(
        generator,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@api_router.get("/health", tags=["Health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
