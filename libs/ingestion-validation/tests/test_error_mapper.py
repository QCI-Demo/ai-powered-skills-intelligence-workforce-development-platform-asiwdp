"""Tests for error mapping utilities."""

from __future__ import annotations

from asiwdp_ingestion.error_mapper import (
    ValidationFailed,
    map_validation_errors,
    tenant_mismatch_body,
    to_http_422,
    validation_error_from_mapping,
)
from asiwdp_ingestion.models import FieldViolation, TenantScopedValidationError


class TestErrorMapper:
    def test_to_http_422_from_model(self) -> None:
        err = TenantScopedValidationError(
            tenant_id="11111111-1111-1111-1111-111111111111",
            contract="employee",
            schema_version="1.0.0",
            message="Payload failed contract validation (1 field error)",
            details=(
                FieldViolation(
                    field="/employee/workEmail",
                    code="format",
                    message="invalid email",
                    schema_path="/properties/employee/properties/workEmail/format",
                ),
            ),
            correlation_id="abc",
        )
        status, body = to_http_422(err)
        assert status == 422
        assert body["error"] == "validation_failed"
        assert body["tenantId"] == err.tenant_id
        assert body["details"][0]["field"] == "/employee/workEmail"
        assert body["details"][0]["schemaPath"].endswith("format")
        assert body["correlationId"] == "abc"

    def test_to_http_422_from_exception(self) -> None:
        err = TenantScopedValidationError(
            tenant_id="t",
            contract="role",
            schema_version="1.0.0",
            message="fail",
            details=(),
        )
        status, body = to_http_422(ValidationFailed(err))
        assert status == 422
        assert body["contract"] == "role"

    def test_map_empty_errors_still_builds_body(self) -> None:
        scoped = map_validation_errors(
            [],
            tenant_id="t1",
            contract="employee",
            schema_version="1.0.0",
            message="custom",
        )
        assert scoped.message == "custom"
        assert scoped.details == ()
        assert scoped.status == 422

    def test_round_trip_serialization(self) -> None:
        err = TenantScopedValidationError(
            tenant_id="11111111-1111-1111-1111-111111111111",
            contract="learning-content",
            schema_version="1.0.0",
            message="Payload failed contract validation (1 field error)",
            details=(
                FieldViolation(field="/content/title", code="required", message="missing"),
            ),
            correlation_id="z",
        )
        restored = validation_error_from_mapping(err.to_dict())
        assert restored.tenant_id == err.tenant_id
        assert restored.contract == err.contract
        assert restored.details[0].field == "/content/title"

    def test_tenant_mismatch_body_omits_foreign_tenant(self) -> None:
        body = tenant_mismatch_body(
            tenant_id="11111111-1111-1111-1111-111111111111",
            correlation_id="c",
        )
        assert body["status"] == 403
        assert body["error"] == "tenant_mismatch"
        assert body["tenantId"] == "11111111-1111-1111-1111-111111111111"
        assert "payloadTenantId" not in body
