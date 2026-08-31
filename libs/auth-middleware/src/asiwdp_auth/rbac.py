"""RBAC policy loader and permission expansion."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

from asiwdp_auth.errors import AuthorizationError


class RbacPolicy:
    """Tenant-scoped role → permission matrix."""

    def __init__(self, matrix: Mapping[str, Any]) -> None:
        if "roles" not in matrix or not isinstance(matrix["roles"], dict):
            raise ValueError("RBAC matrix must contain a 'roles' mapping")
        self._version = str(matrix.get("version", "unknown"))
        self._roles: dict[str, dict[str, Any]] = matrix["roles"]
        self._catalog = set(matrix.get("permission_catalog") or [])
        self._raw = matrix

    @classmethod
    def from_yaml(cls, path: str | Path) -> RbacPolicy:
        matrix_path = Path(path)
        with matrix_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        if not isinstance(data, dict):
            raise ValueError(f"Invalid RBAC matrix at {matrix_path}")
        return cls(data)

    @classmethod
    def from_dict(cls, matrix: Mapping[str, Any]) -> RbacPolicy:
        return cls(matrix)

    @property
    def version(self) -> str:
        return self._version

    def permissions_for_roles(self, roles: tuple[str, ...] | list[str]) -> frozenset[str]:
        granted: set[str] = set()
        for role in roles:
            definition = self._roles.get(role)
            if definition is None:
                continue
            perms = definition.get("permissions") or []
            for perm in perms:
                if isinstance(perm, str) and perm:
                    granted.add(perm)
        return frozenset(granted)

    def expand_effective_permissions(
        self,
        *,
        roles: tuple[str, ...] | list[str],
        scopes: tuple[str, ...] | list[str] = (),
        permissions: tuple[str, ...] | list[str] = (),
    ) -> frozenset[str]:
        """Union of role-implied permissions, token scopes, and explicit permissions."""
        granted = set(self.permissions_for_roles(roles))
        granted.update(s for s in scopes if isinstance(s, str) and s)
        granted.update(p for p in permissions if isinstance(p, str) and p)
        return frozenset(granted)

    def assert_permissions(
        self,
        effective: frozenset[str],
        required: tuple[str, ...] | list[str],
        *,
        require_all: bool = True,
    ) -> None:
        if not required:
            return
        if "*" in effective:
            return
        if require_all:
            missing = [p for p in required if p not in effective]
            if missing:
                raise AuthorizationError(
                    f"Missing required permission(s): {', '.join(missing)}"
                )
        else:
            if not any(p in effective for p in required):
                raise AuthorizationError(
                    f"Requires one of: {', '.join(required)}"
                )

    def role_names(self) -> list[str]:
        return sorted(self._roles.keys())
