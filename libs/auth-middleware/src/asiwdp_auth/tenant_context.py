"""Tenant context extracted from verified JWT claims."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from starlette.requests import Request

from asiwdp_auth.context import Principal
from asiwdp_auth.errors import AuthorizationError, TokenMissingError


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Request-scoped tenant and OAuth2 scope context derived from a JWT.

    Built by middleware after successful token verification so handlers never
    re-parse claim payloads.
    """

    tenant_id: str
    subject: str
    scopes: tuple[str, ...]
    roles: tuple[str, ...]
    effective_permissions: frozenset[str]
    actor_type: str = "user"
    org_id: str | None = None
    session_id: str | None = None

    def has_scope(self, scope: str) -> bool:
        """Return True when the caller holds ``scope`` (or platform ``*``)."""
        if "*" in self.effective_permissions:
            return True
        return scope in self.scopes or scope in self.effective_permissions

    def require_scopes(
        self,
        *scopes: str,
        require_all: bool = True,
    ) -> None:
        """Raise ``AuthorizationError`` when required scopes are missing."""
        if "*" in self.effective_permissions:
            return
        if require_all:
            missing = [s for s in scopes if not self.has_scope(s)]
            if missing:
                raise AuthorizationError(
                    f"Missing required scope(s): {', '.join(missing)}",
                    error_code="scope_denied",
                )
        elif not any(self.has_scope(s) for s in scopes):
            raise AuthorizationError(
                f"Requires one of: {', '.join(scopes)}",
                error_code="scope_denied",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "subject": self.subject,
            "scopes": list(self.scopes),
            "roles": list(self.roles),
            "effective_permissions": sorted(self.effective_permissions),
            "actor_type": self.actor_type,
            "org_id": self.org_id,
            "session_id": self.session_id,
        }

    @classmethod
    def from_principal(cls, principal: Principal) -> TenantContext:
        tenant_id = principal.require_tenant()
        return cls(
            tenant_id=tenant_id,
            subject=principal.subject,
            scopes=principal.scopes,
            roles=principal.roles,
            effective_permissions=principal.effective_permissions,
            actor_type=principal.actor_type,
            org_id=principal.org_id,
            session_id=principal.session_id,
        )


def _get_state_value(request: Request, key: str) -> Any:
    state = request.state
    value = getattr(state, key, None)
    if value is None and isinstance(state, dict):
        value = state.get(key)
    return value


def get_principal(request: Request) -> Principal:
    principal = _get_state_value(request, "principal")
    if principal is None:
        raise TokenMissingError("Unauthenticated request")
    if not isinstance(principal, Principal):
        raise TokenMissingError("Invalid authenticated principal")
    return principal


def get_tenant_context(request: Request) -> TenantContext:
    """Return the tenant context attached by middleware, or derive it."""
    existing = _get_state_value(request, "tenant_context")
    if isinstance(existing, TenantContext):
        return existing
    return TenantContext.from_principal(get_principal(request))


def attach_tenant_context(scope: dict[str, Any], principal: Principal) -> TenantContext:
    """Map JWT principal claims onto ``scope['state'].tenant_context``."""
    context = TenantContext.from_principal(principal)
    state = scope.setdefault("state", {})
    if hasattr(state, "__setattr__") and not isinstance(state, dict):
        setattr(state, "tenant_context", context)
        setattr(state, "tenant_id", context.tenant_id)
        setattr(state, "scopes", context.scopes)
    else:
        state["tenant_context"] = context  # type: ignore[index]
        state["tenant_id"] = context.tenant_id  # type: ignore[index]
        state["scopes"] = context.scopes  # type: ignore[index]
    return context
