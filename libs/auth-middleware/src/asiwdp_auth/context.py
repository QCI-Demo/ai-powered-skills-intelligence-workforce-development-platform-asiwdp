"""Authenticated principal attached to request state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from asiwdp_auth.claims import AccessTokenClaims


@dataclass(frozen=True, slots=True)
class Principal:
    """Resolved security principal for a request."""

    subject: str
    tenant_id: str | None
    roles: tuple[str, ...]
    scopes: tuple[str, ...]
    effective_permissions: frozenset[str]
    actor_type: str
    session_id: str | None = None
    org_id: str | None = None
    claims: AccessTokenClaims | None = None

    def has_permission(self, permission: str) -> bool:
        from asiwdp_auth.rbac import permission_satisfies

        return permission_satisfies(self.effective_permissions, permission)

    def has_any_permission(self, permissions: tuple[str, ...] | list[str]) -> bool:
        return any(self.has_permission(p) for p in permissions)

    def has_all_permissions(self, permissions: tuple[str, ...] | list[str]) -> bool:
        return all(self.has_permission(p) for p in permissions)

    def assert_same_tenant(self, tenant_id: str) -> None:
        """Fail closed when a request tenant does not match the token tenant."""
        from asiwdp_auth.errors import AuthorizationError

        if not self.tenant_id:
            raise AuthorizationError("Principal has no tenant binding")
        if self.tenant_id != tenant_id:
            raise AuthorizationError("Cross-tenant access denied")

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def require_tenant(self) -> str:
        if not self.tenant_id:
            raise ValueError("Principal has no tenant_id")
        return self.tenant_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "tenant_id": self.tenant_id,
            "roles": list(self.roles),
            "scopes": list(self.scopes),
            "effective_permissions": sorted(self.effective_permissions),
            "actor_type": self.actor_type,
            "session_id": self.session_id,
            "org_id": self.org_id,
        }
