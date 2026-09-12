"""RBAC helpers for PlatformAdmin provisioning gate."""

from __future__ import annotations

from typing import Any

# JWT role claim may use PascalCase (PlatformAdmin) or snake_case (platform_admin).
PLATFORM_ADMIN_ROLES = frozenset({"PlatformAdmin", "platform_admin"})


def is_platform_admin(principal: Any) -> bool:
    """Return True when the principal holds PlatformAdmin (or platform_admin)."""
    if principal is None:
        return False
    has_any = getattr(principal, "has_any_role", None)
    if callable(has_any):
        return bool(has_any(PLATFORM_ADMIN_ROLES))
    roles = getattr(principal, "roles", ()) or ()
    return any(role in PLATFORM_ADMIN_ROLES for role in roles)
