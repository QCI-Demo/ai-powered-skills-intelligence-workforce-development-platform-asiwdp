"""FastAPI dependencies: tenant context and controller wiring."""

from __future__ import annotations

from typing import Annotated

from asiwdp_auth import TenantContext, get_tenant_context
from fastapi import Depends, Request

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


def tenant_context_dep(request: Request) -> TenantContext:
    return get_tenant_context(request)


TenantCtx = Annotated[TenantContext, Depends(tenant_context_dep)]


def get_hris_v1() -> HrisV1Controller:
    return HrisV1Controller()


def get_lms_v1() -> LmsV1Controller:
    return LmsV1Controller()


def get_content_v1() -> ContentV1Controller:
    return ContentV1Controller()


def get_hris_v2() -> HrisV2Controller:
    return HrisV2Controller()


def get_lms_v2() -> LmsV2Controller:
    return LmsV2Controller()


def get_content_v2() -> ContentV2Controller:
    return ContentV2Controller()
