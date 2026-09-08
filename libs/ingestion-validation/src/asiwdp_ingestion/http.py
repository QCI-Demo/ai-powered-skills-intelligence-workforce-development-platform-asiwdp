"""Optional Starlette helpers for returning HTTP 422 validation responses."""

from __future__ import annotations

from typing import Any

from asiwdp_ingestion.error_mapper import ValidationFailed, tenant_mismatch_body, to_http_422
from asiwdp_ingestion.errors import TenantMismatchError
from asiwdp_ingestion.models import TenantScopedValidationError, ValidationResult


def validation_json_response(result: ValidationResult) -> Any:
    """Build a Starlette ``JSONResponse`` from a ``ValidationResult``.

    Requires the optional ``starlette`` extra: ``pip install asiwdp-ingestion[starlette]``.
    """
    from starlette.responses import JSONResponse

    status, body = result.to_http_response()
    return JSONResponse(status_code=status, content=body)


def exception_json_response(exc: Exception) -> Any:
    """Map validation / tenant exceptions to Starlette JSON responses."""
    from starlette.responses import JSONResponse

    if isinstance(exc, ValidationFailed):
        status, body = to_http_422(exc)
        return JSONResponse(status_code=status, content=body)
    if isinstance(exc, TenantScopedValidationError):
        status, body = to_http_422(exc)
        return JSONResponse(status_code=status, content=body)
    if isinstance(exc, TenantMismatchError):
        return JSONResponse(
            status_code=exc.status_code,
            content=tenant_mismatch_body(tenant_id=exc.tenant_id, message=exc.message),
        )
    raise exc
