"""Tenant-scoped validation result and error models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


HTTP_UNPROCESSABLE_ENTITY = 422


@dataclass(frozen=True, slots=True)
class FieldViolation:
    """A single JSON Schema validation failure for one field path."""

    field: str
    code: str
    message: str
    schema_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "field": self.field,
            "code": self.code,
            "message": self.message,
        }
        if self.schema_path:
            payload["schemaPath"] = self.schema_path
        return payload


@dataclass(frozen=True, slots=True)
class TenantScopedValidationError:
    """HTTP 422 body: tenant-scoped ingestion validation failure."""

    tenant_id: str
    contract: str
    schema_version: str
    message: str
    details: tuple[FieldViolation, ...]
    correlation_id: str | None = None
    error: str = "validation_failed"
    status: int = HTTP_UNPROCESSABLE_ENTITY

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "error": self.error,
            "message": self.message,
            "status": self.status,
            "tenantId": self.tenant_id,
            "contract": self.contract,
            "schemaVersion": self.schema_version,
            "details": [d.to_dict() for d in self.details],
        }
        if self.correlation_id is not None:
            body["correlationId"] = self.correlation_id
        return body


@dataclass(slots=True)
class ValidationResult:
    """Outcome of validating an ingestion payload against a contract schema."""

    ok: bool
    contract: str
    schema_version: str
    tenant_id: str
    correlation_id: str | None = None
    violations: tuple[FieldViolation, ...] = ()
    error: TenantScopedValidationError | None = None
    validated_payload: Mapping[str, Any] | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_http_response(self) -> tuple[int, dict[str, Any]]:
        """Return ``(status_code, body)`` — 422 on failure, 200 stub on success."""
        if self.ok:
            return 200, {
                "status": "valid",
                "tenantId": self.tenant_id,
                "contract": self.contract,
                "schemaVersion": self.schema_version,
                **(
                    {"correlationId": self.correlation_id}
                    if self.correlation_id is not None
                    else {}
                ),
            }
        assert self.error is not None
        return self.error.status, self.error.to_dict()

    def raise_for_status(self) -> None:
        """Raise ``ValidationFailed`` if the payload is invalid."""
        if not self.ok:
            from asiwdp_ingestion.error_mapper import ValidationFailed

            raise ValidationFailed(self.error)  # type: ignore[arg-type]


def model_as_dict(obj: Any) -> dict[str, Any]:
    """Helper for tests / logging of dataclass models (no PII values)."""
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return asdict(obj)
