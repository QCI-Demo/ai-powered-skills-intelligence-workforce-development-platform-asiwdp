"""PlatformAdmin RBAC helpers for tenant provisioning."""

from __future__ import annotations

from asiwdp_auth.context import Principal
from asiwdp_auth.errors import AuthorizationError

# Story requires PlatformAdmin; S2 matrix uses platform_admin. Accept both.
PLATFORM_ADMIN_ROLES = frozenset({"PlatformAdmin", "platform_admin"})


def is_platform_admin(principal: Principal) -> bool:
    return any(role in PLATFORM_ADMIN_ROLES for role in principal.roles)


def assert_platform_admin(principal: Principal) -> None:
    """Require PlatformAdmin role; raise AuthorizationError (403) otherwise."""
    if is_platform_admin(principal):
        return
    # Wildcard permission alone is insufficient without the PlatformAdmin role
    # for this privileged cross-tenant provisioning operation.
    raise AuthorizationError(
        "PlatformAdmin role required to provision tenants"
    )
