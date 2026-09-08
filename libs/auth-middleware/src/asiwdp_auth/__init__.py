"""ASIWDP OAuth2/JWT authentication middleware with tenant-scoped RBAC."""

from asiwdp_auth.claims import AccessTokenClaims
from asiwdp_auth.config import AuthConfig
from asiwdp_auth.context import Principal
from asiwdp_auth.errors import (
    AuthenticationError,
    AuthorizationError,
    ClaimValidationError,
    TokenExpiredError,
    TokenInvalidError,
    TokenMissingError,
)
from asiwdp_auth.jwt_verifier import JwtVerifier
from asiwdp_auth.middleware import AuthMiddleware, require_permission
from asiwdp_auth.rbac import RbacPolicy, permission_satisfies

__all__ = [
    "AccessTokenClaims",
    "AuthConfig",
    "AuthMiddleware",
    "AuthenticationError",
    "AuthorizationError",
    "ClaimValidationError",
    "JwtVerifier",
    "Principal",
    "RbacPolicy",
    "TokenExpiredError",
    "TokenInvalidError",
    "TokenMissingError",
    "permission_satisfies",
    "require_permission",
]

__version__ = "0.1.0"
