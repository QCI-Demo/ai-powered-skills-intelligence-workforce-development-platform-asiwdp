"""ASIWDP OAuth2/JWT authentication middleware with tenant-scoped RBAC."""

from asiwdp_auth.api_version import API_VERSION_HEADER, ApiVersionMiddleware, resolve_api_version
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
from asiwdp_auth.middleware import AuthMiddleware, require_permission, require_scope
from asiwdp_auth.rbac import RbacPolicy
from asiwdp_auth.tenant_context import TenantContext, get_tenant_context

__all__ = [
    "API_VERSION_HEADER",
    "AccessTokenClaims",
    "ApiVersionMiddleware",
    "AuthConfig",
    "AuthMiddleware",
    "AuthenticationError",
    "AuthorizationError",
    "ClaimValidationError",
    "JwtVerifier",
    "Principal",
    "RbacPolicy",
    "TenantContext",
    "TokenExpiredError",
    "TokenInvalidError",
    "TokenMissingError",
    "get_tenant_context",
    "require_permission",
    "require_scope",
    "resolve_api_version",
]

__version__ = "0.2.0"
