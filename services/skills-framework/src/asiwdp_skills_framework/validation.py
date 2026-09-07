"""JSON Schema validation helpers for request bodies and import rows."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError

_SCHEMA_DIR = Path(__file__).resolve().parent / "json_schemas"


@lru_cache(maxsize=16)
def _load_schema(name: str) -> dict[str, Any]:
    path = _SCHEMA_DIR / f"{name}.json"
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def validate_against_schema(payload: dict[str, Any], schema_name: str) -> list[str]:
    """Return a list of human-readable validation errors (empty if valid)."""
    schema = _load_schema(schema_name)
    validator = Draft202012Validator(schema)
    errors: list[str] = []
    for err in sorted(validator.iter_errors(payload), key=lambda e: list(e.path)):
        location = ".".join(str(p) for p in err.path) or "(root)"
        errors.append(f"{location}: {err.message}")
    return errors


def assert_valid_schema(payload: dict[str, Any], schema_name: str) -> None:
    errors = validate_against_schema(payload, schema_name)
    if errors:
        raise JsonSchemaValidationError("; ".join(errors))


def validate_import_row(
    row: dict[str, Any],
    *,
    entity_type: str,
    expected_tenant_id: UUID,
    expected_version: int,
) -> list[str]:
    """Validate a single import row against domain rules + JSON schema."""
    errors: list[str] = []

    tenant_raw = row.get("tenant_id")
    if tenant_raw is None or tenant_raw == "":
        errors.append("tenant_id is required")
    else:
        try:
            tenant = UUID(str(tenant_raw))
            if tenant != expected_tenant_id:
                errors.append(
                    f"tenant_id '{tenant}' does not match authenticated tenant "
                    f"'{expected_tenant_id}'"
                )
        except (ValueError, TypeError):
            errors.append(f"tenant_id '{tenant_raw}' is not a valid UUID")

    version_raw = row.get("version")
    if version_raw is None or version_raw == "":
        errors.append("version is required")
    else:
        try:
            version = int(version_raw)
            if version < 1:
                errors.append("version must be >= 1")
            elif version != expected_version:
                errors.append(
                    f"version {version} does not match import version {expected_version}"
                )
        except (TypeError, ValueError):
            errors.append(f"version '{version_raw}' is not an integer")

    schema_name = {
        "skill": "skill_import_row",
        "category": "category_import_row",
        "proficiency": "proficiency_import_row",
    }.get(entity_type)
    if schema_name is None:
        errors.append(f"unsupported entity_type '{entity_type}'")
        return errors

    # Coerce numeric strings for schema validation on CSV rows
    coerced = dict(row)
    for key in ("version", "level", "rank_order"):
        if key in coerced and isinstance(coerced[key], str) and coerced[key].isdigit():
            coerced[key] = int(coerced[key])

    errors.extend(validate_against_schema(coerced, schema_name))
    return errors
