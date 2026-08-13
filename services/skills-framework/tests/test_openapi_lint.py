"""Ensure the published OpenAPI document validates."""

from __future__ import annotations

from pathlib import Path

from openapi_spec_validator import validate
from openapi_spec_validator.readers import read_from_filename

ROOT = Path(__file__).resolve().parents[3]
SPEC = ROOT / "openapi" / "skills-framework-service.yaml"


def test_skills_framework_openapi_validates():
    spec_dict, _ = read_from_filename(str(SPEC))
    validate(spec_dict)
    assert "X-Taxonomy-Version" in str(spec_dict)
    assert "/taxonomy/export" in spec_dict["paths"]
    assert "/taxonomy/import" in spec_dict["paths"]
    assert "/categories" in spec_dict["paths"]
    assert "/proficiencies" in spec_dict["paths"]
