"""Validate ingestion payloads against contract JSON Schemas."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from asiwdp_ingestion.error_mapper import map_validation_errors
from asiwdp_ingestion.errors import TenantMismatchError
from asiwdp_ingestion.models import ValidationResult
from asiwdp_ingestion.schema_registry import SchemaRegistry


class IngestionValidator:
    """Loads schemas from the contract registry and validates incoming payloads.

    Flow:
      1. Resolve contract id → compiled Draft 2020-12 validator
      2. Enforce tenant scope (payload ``tenantId`` == authenticated tenant)
      3. Collect all JSON Schema errors (``iter_errors``)
      4. Map errors to ``TenantScopedValidationError`` (HTTP 422)
    """

    def __init__(self, registry: SchemaRegistry) -> None:
        self.registry = registry

    @classmethod
    def from_contracts_root(
        cls,
        contracts_root: str | Path | None = None,
        **kwargs: Any,
    ) -> IngestionValidator:
        return cls(SchemaRegistry.from_contracts_root(contracts_root, **kwargs))

    def validate(
        self,
        contract: str,
        payload: Mapping[str, Any] | Any,
        *,
        tenant_id: str,
        correlation_id: str | None = None,
        enforce_tenant_match: bool = True,
        raise_on_tenant_mismatch: bool = True,
    ) -> ValidationResult:
        """Validate ``payload`` against ``contract`` for ``tenant_id``.

        Parameters
        ----------
        contract:
            Contract id (`employee`, `role`, `learning-content`, `learner-activity`).
        payload:
            Incoming JSON object (dict-like).
        tenant_id:
            Authenticated tenant from the JWT / request context.
        correlation_id:
            Optional request correlation id for the error model.
        enforce_tenant_match:
            When True, require ``payload["tenantId"] == tenant_id``.
        raise_on_tenant_mismatch:
            When True (default), raise ``TenantMismatchError`` (HTTP 403).
            When False, return a failed ``ValidationResult`` (still not 422).
        """
        if not isinstance(payload, Mapping):
            from asiwdp_ingestion.models import FieldViolation, TenantScopedValidationError

            error = TenantScopedValidationError(
                tenant_id=tenant_id,
                contract=contract,
                schema_version=self.registry.schema_version,
                message="Payload must be a JSON object",
                details=(
                    FieldViolation(
                        field="/",
                        code="type",
                        message="Payload must be a JSON object",
                    ),
                ),
                correlation_id=correlation_id,
            )
            return ValidationResult(
                ok=False,
                contract=contract,
                schema_version=self.registry.schema_version,
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                violations=error.details,
                error=error,
            )

        validator = self.registry.get_validator(contract)

        if enforce_tenant_match:
            payload_tenant = payload.get("tenantId")
            if payload_tenant != tenant_id:
                mismatch = TenantMismatchError(
                    "Payload tenantId does not match authenticated tenant",
                    tenant_id=tenant_id,
                    payload_tenant_id=str(payload_tenant)
                    if payload_tenant is not None
                    else None,
                )
                if raise_on_tenant_mismatch:
                    raise mismatch
                return ValidationResult(
                    ok=False,
                    contract=contract,
                    schema_version=self.registry.schema_version,
                    tenant_id=tenant_id,
                    correlation_id=correlation_id,
                    meta={"tenant_mismatch": True},
                )

        errors = list(validator.iter_errors(payload))
        if not errors:
            return ValidationResult(
                ok=True,
                contract=contract,
                schema_version=self.registry.schema_version,
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                validated_payload=dict(payload),
            )

        scoped = map_validation_errors(
            errors,
            tenant_id=tenant_id,
            contract=contract,
            schema_version=self.registry.schema_version,
            correlation_id=correlation_id,
        )
        return ValidationResult(
            ok=False,
            contract=contract,
            schema_version=self.registry.schema_version,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            violations=scoped.details,
            error=scoped,
        )

    def validate_or_raise(
        self,
        contract: str,
        payload: Mapping[str, Any] | Any,
        *,
        tenant_id: str,
        correlation_id: str | None = None,
    ) -> Mapping[str, Any]:
        """Validate and return the payload, or raise ``ValidationFailed`` / tenant errors."""
        result = self.validate(
            contract,
            payload,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )
        result.raise_for_status()
        assert result.validated_payload is not None
        return result.validated_payload
