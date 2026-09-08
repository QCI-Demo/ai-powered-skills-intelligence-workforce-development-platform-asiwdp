"""Error types for consent-aware personal data handling."""

from __future__ import annotations

from typing import Any
from uuid import UUID


class PersonalDataError(Exception):
    """Base class for personal-data domain failures."""

    status_code: int = 400
    error_code: str = "personal_data_error"

    def __init__(self, message: str, *, error_code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if error_code is not None:
            self.error_code = error_code

    def to_error_body(self) -> dict[str, Any]:
        return {"error": self.error_code, "message": self.message}


class ConsentMissingError(PersonalDataError):
    """Valid consent is required before persisting personal skill data (HTTP 422)."""

    status_code: int = 422
    error_code: str = "consent_missing"

    def __init__(
        self,
        message: str = "Valid consent required before persisting personal skill data",
        *,
        tenant_id: UUID | None = None,
        subject_id: UUID | None = None,
        purpose: str | None = None,
    ) -> None:
        super().__init__(message)
        self.tenant_id = tenant_id
        self.subject_id = subject_id
        self.purpose = purpose

    def to_error_body(self) -> dict[str, Any]:
        body = super().to_error_body()
        if self.purpose is not None:
            body["purpose"] = self.purpose
        if self.subject_id is not None:
            body["subject_id"] = str(self.subject_id)
        if self.tenant_id is not None:
            body["tenant_id"] = str(self.tenant_id)
        return body
