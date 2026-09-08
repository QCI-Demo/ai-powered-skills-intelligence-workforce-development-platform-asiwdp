"""ASIWDP ingestion validation: contract schemas → payload checks → HTTP 422 errors."""

from asiwdp_ingestion.error_mapper import map_validation_errors, to_http_422
from asiwdp_ingestion.errors import (
    ContractNotFoundError,
    IngestionValidationError,
    SchemaLoadError,
    TenantMismatchError,
)
from asiwdp_ingestion.models import (
    FieldViolation,
    TenantScopedValidationError,
    ValidationResult,
)
from asiwdp_ingestion.schema_registry import SchemaRegistry
from asiwdp_ingestion.validator import IngestionValidator

__all__ = [
    "ContractNotFoundError",
    "FieldViolation",
    "IngestionValidationError",
    "IngestionValidator",
    "SchemaLoadError",
    "SchemaRegistry",
    "TenantMismatchError",
    "TenantScopedValidationError",
    "ValidationResult",
    "map_validation_errors",
    "to_http_422",
]

__version__ = "0.1.0"
