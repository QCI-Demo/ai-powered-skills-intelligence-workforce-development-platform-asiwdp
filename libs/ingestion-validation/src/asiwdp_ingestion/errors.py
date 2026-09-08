"""Exception types for the ingestion validation layer."""

from __future__ import annotations


class IngestionValidationError(Exception):
    """Base class for ingestion validation failures."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class SchemaLoadError(IngestionValidationError):
    """Contract schema could not be loaded or compiled."""


class ContractNotFoundError(IngestionValidationError):
    """Requested contract id is not registered."""


class TenantMismatchError(IngestionValidationError):
    """Payload tenantId does not match the authenticated tenant scope."""

    status_code: int = 403
    error_code: str = "tenant_mismatch"

    def __init__(
        self,
        message: str,
        *,
        tenant_id: str,
        payload_tenant_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.tenant_id = tenant_id
        self.payload_tenant_id = payload_tenant_id
