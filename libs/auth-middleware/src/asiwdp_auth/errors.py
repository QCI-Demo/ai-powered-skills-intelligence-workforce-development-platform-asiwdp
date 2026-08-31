"""Authentication and authorization error types."""

from __future__ import annotations


class AuthenticationError(Exception):
    """Base class for authentication failures (HTTP 401)."""

    status_code: int = 401
    error_code: str = "unauthenticated"

    def __init__(self, message: str, *, error_code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if error_code is not None:
            self.error_code = error_code


class TokenMissingError(AuthenticationError):
    """Authorization header or bearer token is missing."""

    error_code = "token_missing"


class TokenInvalidError(AuthenticationError):
    """Token signature or structure is invalid / tampered."""

    error_code = "token_invalid"


class TokenExpiredError(AuthenticationError):
    """Token exp claim is in the past."""

    error_code = "token_expired"


class ClaimValidationError(AuthenticationError):
    """Required claims are missing or malformed."""

    error_code = "claims_invalid"


class AuthorizationError(Exception):
    """Authenticated principal lacks required permission (HTTP 403)."""

    status_code: int = 403
    error_code: str = "forbidden"

    def __init__(self, message: str, *, error_code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if error_code is not None:
            self.error_code = error_code
