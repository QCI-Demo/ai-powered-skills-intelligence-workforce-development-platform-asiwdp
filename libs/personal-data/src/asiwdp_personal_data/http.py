"""Starlette helpers that map consent failures to HTTP 422."""

from __future__ import annotations

from starlette.responses import JSONResponse

from asiwdp_personal_data.errors import ConsentMissingError, PersonalDataError


def consent_error_response(exc: ConsentMissingError) -> JSONResponse:
    """Return a 422 Unprocessable Entity response for missing consent."""
    return JSONResponse(status_code=exc.status_code, content=exc.to_error_body())


def personal_data_error_response(exc: PersonalDataError) -> JSONResponse:
    """Map any PersonalDataError to a JSON HTTP response."""
    return JSONResponse(status_code=exc.status_code, content=exc.to_error_body())
