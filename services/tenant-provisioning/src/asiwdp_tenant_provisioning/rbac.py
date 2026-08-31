"""RBAC helpers for PlatformAdmin provisioning gate."""

from __future__ import annotations

from typing import Any

PLATFORM_ADMIN_ROLES = frozenset({"PlatformAdmin", "platform_admin"})


def is_platform_admin(principal: Any) -> bool:
    """Return True when the principal holds PlatformAdmin (or platform_admin)."""
    if principal is None:
        return False
    roles = getattr(principal, "roles", ()) or ()
    return any(role in PLATFORM_ADMIN_ROLES for role in roles)
