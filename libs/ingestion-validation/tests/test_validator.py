"""Tests for SchemaRegistry and IngestionValidator."""

from __future__ import annotations

import pytest

from asiwdp_ingestion import IngestionValidator, SchemaRegistry
from asiwdp_ingestion.errors import ContractNotFoundError, TenantMismatchError
from asiwdp_ingestion.schema_registry import DEFAULT_CONTRACTS


class TestSchemaRegistry:
    def test_loads_all_default_contracts(self, registry: SchemaRegistry) -> None:
        assert set(registry.contract_ids) == set(DEFAULT_CONTRACTS)
        for contract_id in DEFAULT_CONTRACTS:
            validator = registry.get_validator(contract_id)
            assert validator is not None

    def test_unknown_contract_raises(self, registry: SchemaRegistry) -> None:
        with pytest.raises(ContractNotFoundError):
            registry.get_validator("unknown-contract")

    def test_from_contracts_root(self, contracts_root) -> None:
        reg = SchemaRegistry.from_contracts_root(contracts_root)
        assert "employee" in reg.contract_ids


class TestIngestionValidator:
    def test_valid_employee(self, validator: IngestionValidator, valid_employee: dict) -> None:
        result = validator.validate(
            "employee",
            valid_employee,
            tenant_id=valid_employee["tenantId"],
            correlation_id="c-1",
        )
        assert result.ok is True
        assert result.validated_payload is not None
        status, body = result.to_http_response()
        assert status == 200
        assert body["status"] == "valid"
        assert body["contract"] == "employee"

    def test_valid_role(self, validator: IngestionValidator, valid_role: dict) -> None:
        result = validator.validate(
            "role", valid_role, tenant_id=valid_role["tenantId"]
        )
        assert result.ok is True

    def test_valid_learning_content(
        self, validator: IngestionValidator, valid_learning_content: dict
    ) -> None:
        result = validator.validate(
            "learning-content",
            valid_learning_content,
            tenant_id=valid_learning_content["tenantId"],
        )
        assert result.ok is True

    def test_valid_learner_activity(
        self, validator: IngestionValidator, valid_learner_activity: dict
    ) -> None:
        result = validator.validate(
            "learner-activity",
            valid_learner_activity,
            tenant_id=valid_learner_activity["tenantId"],
        )
        assert result.ok is True

    def test_missing_required_field_returns_422(
        self, validator: IngestionValidator, valid_employee: dict
    ) -> None:
        bad = dict(valid_employee)
        employee = dict(bad["employee"])
        del employee["workEmail"]
        bad["employee"] = employee

        result = validator.validate(
            "employee",
            bad,
            tenant_id=bad["tenantId"],
            correlation_id="corr-x",
        )
        assert result.ok is False
        status, body = result.to_http_response()
        assert status == 422
        assert body["error"] == "validation_failed"
        assert body["tenantId"] == bad["tenantId"]
        assert body["contract"] == "employee"
        assert body["schemaVersion"] == "1.0.0"
        assert body["correlationId"] == "corr-x"
        assert body["status"] == 422
        fields = {d["field"] for d in body["details"]}
        assert "/employee" in fields or any(
            f.startswith("/employee") for f in fields
        )
        # PII-safe: no rejected instance values in the body
        for detail in body["details"]:
            assert "rejectedValue" not in detail
            assert "instance" not in detail

    def test_invalid_email_format(
        self, validator: IngestionValidator, valid_employee: dict
    ) -> None:
        bad = dict(valid_employee)
        employee = dict(bad["employee"])
        employee["workEmail"] = "not-an-email"
        bad["employee"] = employee

        result = validator.validate("employee", bad, tenant_id=bad["tenantId"])
        assert result.ok is False
        status, body = result.to_http_response()
        assert status == 422
        codes = {d["code"] for d in body["details"]}
        assert "format" in codes
        email_details = [
            d for d in body["details"] if d["field"] == "/employee/workEmail"
        ]
        assert email_details

    def test_invalid_enum(
        self, validator: IngestionValidator, valid_role: dict
    ) -> None:
        bad = dict(valid_role)
        role = dict(bad["role"])
        role["status"] = "deleted"
        bad["role"] = role

        result = validator.validate("role", bad, tenant_id=bad["tenantId"])
        assert result.ok is False
        assert any(d.code == "enum" for d in result.error.details)  # type: ignore[union-attr]

    def test_tenant_mismatch_raises(
        self, validator: IngestionValidator, valid_employee: dict
    ) -> None:
        with pytest.raises(TenantMismatchError) as exc_info:
            validator.validate(
                "employee",
                valid_employee,
                tenant_id="22222222-2222-2222-2222-222222222222",
            )
        assert exc_info.value.status_code == 403
        assert exc_info.value.error_code == "tenant_mismatch"

    def test_tenant_mismatch_soft(
        self, validator: IngestionValidator, valid_employee: dict
    ) -> None:
        result = validator.validate(
            "employee",
            valid_employee,
            tenant_id="22222222-2222-2222-2222-222222222222",
            raise_on_tenant_mismatch=False,
        )
        assert result.ok is False
        assert result.meta.get("tenant_mismatch") is True

    def test_non_object_payload(self, validator: IngestionValidator) -> None:
        result = validator.validate(
            "employee",
            ["not", "an", "object"],
            tenant_id="11111111-1111-1111-1111-111111111111",
        )
        assert result.ok is False
        status, body = result.to_http_response()
        assert status == 422
        assert body["details"][0]["field"] == "/"

    def test_validate_or_raise_success(
        self, validator: IngestionValidator, valid_employee: dict
    ) -> None:
        payload = validator.validate_or_raise(
            "employee", valid_employee, tenant_id=valid_employee["tenantId"]
        )
        assert payload["employee"]["externalEmployeeId"] == "E-1001"

    def test_validate_or_raise_failure(
        self, validator: IngestionValidator, valid_employee: dict
    ) -> None:
        from asiwdp_ingestion.error_mapper import ValidationFailed

        bad = dict(valid_employee)
        del bad["sourceSystem"]
        with pytest.raises(ValidationFailed) as exc_info:
            validator.validate_or_raise(
                "employee", bad, tenant_id=bad["tenantId"]
            )
        assert exc_info.value.status_code == 422
        assert "details" in exc_info.value.to_dict()

    def test_additional_properties_rejected(
        self, validator: IngestionValidator, valid_employee: dict
    ) -> None:
        bad = dict(valid_employee)
        bad["unexpected"] = True
        result = validator.validate("employee", bad, tenant_id=bad["tenantId"])
        assert result.ok is False
        assert any(
            d.code == "additionalProperties" for d in result.error.details  # type: ignore[union-attr]
        )

    def test_activity_progress_bounds(
        self, validator: IngestionValidator, valid_learner_activity: dict
    ) -> None:
        bad = dict(valid_learner_activity)
        activity = dict(bad["activity"])
        activity["progressPercent"] = 150
        bad["activity"] = activity
        result = validator.validate(
            "learner-activity", bad, tenant_id=bad["tenantId"]
        )
        assert result.ok is False
        assert any(
            d.field == "/activity/progressPercent" for d in result.error.details  # type: ignore[union-attr]
        )
