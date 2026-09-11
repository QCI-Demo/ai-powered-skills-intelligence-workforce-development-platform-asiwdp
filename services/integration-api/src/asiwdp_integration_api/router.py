"""Versioned API routers for Integration APIs."""

from __future__ import annotations

from typing import Annotated, Any

from asiwdp_auth import require_scope
from fastapi import APIRouter, Depends, Request, status

from asiwdp_integration_api.controllers.v1 import (
    ContentV1Controller,
    HrisV1Controller,
    LmsV1Controller,
)
from asiwdp_integration_api.controllers.v2 import (
    ContentV2Controller,
    HrisV2Controller,
    LmsV2Controller,
)
from asiwdp_integration_api.deps import (
    TenantCtx,
    get_content_v1,
    get_content_v2,
    get_hris_v1,
    get_hris_v2,
    get_lms_v1,
    get_lms_v2,
)
from asiwdp_integration_api.schemas.models import (
    BatchRequest,
    ContentCatalogRecord,
    CredentialRotateRequest,
    EmployeeRecord,
    LearnerActivityRecord,
    RoleRecord,
)

v1_router = APIRouter(prefix="/v1", tags=["Integration API v1"])
v2_router = APIRouter(prefix="/v2", tags=["Integration API v2"])


@v1_router.get("/health", tags=["Health"])
def v1_health() -> dict[str, str]:
    return {"status": "ok", "service": "integration-api", "apiVersion": "v1"}


@v1_router.post(
    "/hris/employees",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest HRIS employee (v1)",
)
@require_scope("hris:write")
def post_hris_employee_v1(
    request: Request,
    body: EmployeeRecord,
    tenant: TenantCtx,
    controller: Annotated[HrisV1Controller, Depends(get_hris_v1)],
) -> dict[str, Any]:
    return controller.ingest_employee(tenant, body)


@v1_router.get(
    "/hris/employees",
    summary="List HRIS employees for tenant (v1)",
)
@require_scope("hris:read")
def list_hris_employees_v1(
    request: Request,
    tenant: TenantCtx,
    controller: Annotated[HrisV1Controller, Depends(get_hris_v1)],
) -> dict[str, Any]:
    return controller.list_employees(tenant)


@v1_router.post(
    "/hris/roles",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest HRIS role (v1)",
)
@require_scope("hris:write")
def post_hris_role_v1(
    request: Request,
    body: RoleRecord,
    tenant: TenantCtx,
    controller: Annotated[HrisV1Controller, Depends(get_hris_v1)],
) -> dict[str, Any]:
    return controller.ingest_role(tenant, body)


@v1_router.post(
    "/lms/activities",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest LMS learner activity (v1)",
)
@require_scope("lms:write")
def post_lms_activity_v1(
    request: Request,
    body: LearnerActivityRecord,
    tenant: TenantCtx,
    controller: Annotated[LmsV1Controller, Depends(get_lms_v1)],
) -> dict[str, Any]:
    return controller.ingest_activity(tenant, body)


@v1_router.get(
    "/lms/content",
    summary="List LMS content for tenant (v1)",
)
@require_scope("lms:read")
def list_lms_content_v1(
    request: Request,
    tenant: TenantCtx,
    controller: Annotated[LmsV1Controller, Depends(get_lms_v1)],
) -> dict[str, Any]:
    return controller.list_content(tenant)


@v1_router.post(
    "/content/catalog",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upsert content catalog record (v1)",
)
@require_scope("content:write")
def post_content_catalog_v1(
    request: Request,
    body: ContentCatalogRecord,
    tenant: TenantCtx,
    controller: Annotated[ContentV1Controller, Depends(get_content_v1)],
) -> dict[str, Any]:
    return controller.upsert_catalog(tenant, body)


@v1_router.post(
    "/integrations/credentials/rotate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Rotate integration credential via secret manager (v1)",
)
@require_scope("integrations:credentials:rotate")
def rotate_credential_v1(
    request: Request,
    body: CredentialRotateRequest,
    tenant: TenantCtx,
    controller: Annotated[ContentV1Controller, Depends(get_content_v1)],
) -> dict[str, Any]:
    return controller.rotate_credential(tenant, body)


@v2_router.get("/health", tags=["Health"])
def v2_health() -> dict[str, str]:
    return {"status": "ok", "service": "integration-api", "apiVersion": "v2"}


@v2_router.post(
    "/hris/employees/batch",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Batch ingest HRIS employees (v2)",
)
@require_scope("hris:write")
def post_hris_employee_batch_v2(
    request: Request,
    body: BatchRequest,
    tenant: TenantCtx,
    controller: Annotated[HrisV2Controller, Depends(get_hris_v2)],
) -> dict[str, Any]:
    return controller.ingest_employee_batch(tenant, body)


@v2_router.get(
    "/hris/employees/batches/{correlation_id}/status",
    summary="HRIS employee batch processing status (v2)",
)
@require_scope("hris:read")
def get_hris_batch_status_v2(
    request: Request,
    correlation_id: str,
    tenant: TenantCtx,
    controller: Annotated[HrisV2Controller, Depends(get_hris_v2)],
) -> dict[str, Any]:
    return controller.batch_status(tenant, correlation_id)


@v2_router.post(
    "/lms/activities/batch",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Batch ingest LMS learner activities (v2)",
)
@require_scope("lms:write")
def post_lms_activity_batch_v2(
    request: Request,
    body: BatchRequest,
    tenant: TenantCtx,
    controller: Annotated[LmsV2Controller, Depends(get_lms_v2)],
) -> dict[str, Any]:
    return controller.ingest_activity_batch(tenant, body)


@v2_router.post(
    "/content/catalog/batch",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Batch upsert content catalog (v2)",
)
@require_scope("content:write")
def post_content_catalog_batch_v2(
    request: Request,
    body: BatchRequest,
    tenant: TenantCtx,
    controller: Annotated[ContentV2Controller, Depends(get_content_v2)],
) -> dict[str, Any]:
    return controller.upsert_catalog_batch(tenant, body)
