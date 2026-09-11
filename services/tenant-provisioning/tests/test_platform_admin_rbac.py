"""Unit tests for PlatformAdmin RBAC helper."""

from __future__ import annotations

from types import SimpleNamespace

from asiwdp_auth.context import Principal
from asiwdp_tenant_provisioning.rbac import is_platform_admin


def test_is_platform_admin_accepts_pascal_and_snake() -> None:
    assert is_platform_admin(SimpleNamespace(roles=("PlatformAdmin",)))
    assert is_platform_admin(SimpleNamespace(roles=("platform_admin",)))
    assert is_platform_admin(
        SimpleNamespace(roles=("learner", "PlatformAdmin"))
    )


def test_is_platform_admin_rejects_tenant_roles() -> None:
    assert not is_platform_admin(None)
    assert not is_platform_admin(SimpleNamespace(roles=()))
    assert not is_platform_admin(SimpleNamespace(roles=("tenant_admin",)))
    assert not is_platform_admin(SimpleNamespace(roles=("org_admin", "learner")))


def test_is_platform_admin_uses_principal_has_any_role() -> None:
    principal = Principal(
        subject="u1",
        tenant_id=None,
        roles=("PlatformAdmin",),
        scopes=(),
        effective_permissions=frozenset({"*"}),
        actor_type="user",
    )
    assert is_platform_admin(principal)
    denied = Principal(
        subject="u2",
        tenant_id="t1",
        roles=("tenant_admin",),
        scopes=(),
        effective_permissions=frozenset({"tenants:write"}),
        actor_type="user",
    )
    assert not is_platform_admin(denied)
