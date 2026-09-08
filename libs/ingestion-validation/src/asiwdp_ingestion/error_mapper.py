"""Map JSON Schema errors to the tenant-scoped HTTP 422 error model.

Field details include JSON Pointer paths and keyword codes. Rejected instance
values are intentionally omitted to avoid leaking PII in API responses or logs.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from jsonschema.exceptions import ValidationError as JsonSchemaValidationError

from asiwdp_ingestion.models import (
    HTTP_UNPROCESSABLE_ENTITY,
    FieldViolation,
    TenantScopedValidationError,
)


class ValidationFailed(Exception):
    """Raised when an ingestion payload fails contract validation (HTTP 422)."""

    status_code: int = HTTP_UNPROCESSABLE_ENTITY
    error_code: str = "validation_failed"

    def __init__(self, error: TenantScopedValidationError) -> None:
        super().__init__(error.message)
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        return self.error.to_dict()


def _json_pointer(absolute_path: Sequence[Any]) -> str:
    """Convert jsonschema ``absolute_path`` to a JSON Pointer (RFC 6901)."""
    if not absolute_path:
        return "/"
    parts: list[str] = []
    for part in absolute_path:
        token = str(part).replace("~", "~0").replace("/", "~1")
        parts.append(token)
    return "/" + "/".join(parts)


def _schema_path(relative_schema_path: Sequence[Any]) -> str | None:
    if not relative_schema_path:
        return None
    return "/" + "/".join(str(p) for p in relative_schema_path)


def map_validation_errors(
    errors: Iterable[JsonSchemaValidationError],
    *,
    tenant_id: str,
    contract: str,
    schema_version: str,
    correlation_id: str | None = None,
    message: str | None = None,
    max_errors: int = 50,
) -> TenantScopedValidationError:
    """Convert jsonschema ``ValidationError``s into a tenant-scoped 422 model.

    Errors are sorted by field path for stable responses. At most ``max_errors``
    details are included (full count reflected in the summary message).
    """
    collected = sorted(errors, key=lambda e: list(e.absolute_path))
    total = len(collected)
    truncated = collected[:max_errors]

    details: list[FieldViolation] = []
    for err in truncated:
        details.append(
            FieldViolation(
                field=_json_pointer(list(err.absolute_path)),
                code=err.validator or "invalid",
                message=err.message,
                schema_path=_schema_path(list(err.relative_schema_path)),
            )
        )

    if message is None:
        if total == 0:
            message = "Payload failed contract validation"
        elif total == 1:
            message = "Payload failed contract validation (1 field error)"
        else:
            shown = len(details)
            suffix = f", showing {shown}" if shown < total else ""
            message = (
                f"Payload failed contract validation ({total} field errors{suffix})"
            )

    return TenantScopedValidationError(
        tenant_id=tenant_id,
        contract=contract,
        schema_version=schema_version,
        message=message,
        details=tuple(details),
        correlation_id=correlation_id,
    )


def to_http_422(
    error: TenantScopedValidationError | ValidationFailed,
) -> tuple[int, dict[str, Any]]:
    """Return ``(422, body)`` suitable for Starlette/FastAPI JSON responses."""
    if isinstance(error, ValidationFailed):
        body = error.to_dict()
    else:
        body = error.to_dict()
    return HTTP_UNPROCESSABLE_ENTITY, body


def tenant_mismatch_body(
    *,
    tenant_id: str,
    correlation_id: str | None = None,
    message: str = "Payload tenantId does not match authenticated tenant",
) -> dict[str, Any]:
    """Body for tenant-scope failures (HTTP 403) — no payload tenant echoed."""
    body: dict[str, Any] = {
        "error": "tenant_mismatch",
        "message": message,
        "status": 403,
        "tenantId": tenant_id,
    }
    if correlation_id is not None:
        body["correlationId"] = correlation_id
    return body


def validation_error_from_mapping(data: Mapping[str, Any]) -> TenantScopedValidationError:
    """Rebuild a ``TenantScopedValidationError`` from a previously serialized body."""
    details_raw = data.get("details") or []
    details = tuple(
        FieldViolation(
            field=str(item["field"]),
            code=str(item["code"]),
            message=str(item["message"]),
            schema_path=item.get("schemaPath"),
        )
        for item in details_raw
    )
    return TenantScopedValidationError(
        tenant_id=str(data["tenantId"]),
        contract=str(data["contract"]),
        schema_version=str(data["schemaVersion"]),
        message=str(data.get("message", "Payload failed contract validation")),
        details=details,
        correlation_id=data.get("correlationId"),
        error=str(data.get("error", "validation_failed")),
        status=int(data.get("status", HTTP_UNPROCESSABLE_ENTITY)),
    )
