"""ASGI/Starlette authentication middleware and permission decorator."""

from __future__ import annotations

import asyncio
import functools
from pathlib import Path
from typing import Any, Callable, Iterable

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from asiwdp_auth.config import AuthConfig
from asiwdp_auth.errors import (
    AuthenticationError,
    AuthorizationError,
    TokenMissingError,
)
from asiwdp_auth.jwt_verifier import JwtVerifier
from asiwdp_auth.rbac import RbacPolicy


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise TokenMissingError("Missing Authorization header")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise TokenMissingError("Authorization header must be Bearer <token>")
    return parts[1].strip()


def _error_response(exc: Exception) -> JSONResponse:
    if isinstance(exc, AuthenticationError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.error_code, "message": exc.message},
            headers={"WWW-Authenticate": "Bearer"},
        )
    if isinstance(exc, AuthorizationError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.error_code, "message": exc.message},
        )
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "message": "Unexpected auth failure"},
    )


def _get_principal(request: Request) -> Any:
    state = request.state
    principal = getattr(state, "principal", None)
    if principal is None and isinstance(state, dict):
        principal = state.get("principal")
    return principal


class AuthMiddleware:
    """Starlette/ASGI middleware that validates JWTs and enforces optional RBAC."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        config: AuthConfig,
        rbac_matrix_path: str | Path | None = None,
        policy: RbacPolicy | None = None,
        verifier: JwtVerifier | None = None,
        required_permissions: Iterable[str] | None = None,
    ) -> None:
        if policy is None:
            if rbac_matrix_path is None:
                raise ValueError("Either policy or rbac_matrix_path is required")
            policy = RbacPolicy.from_yaml(rbac_matrix_path)
        self.app = app
        self.config = config
        self.policy = policy
        self.verifier = verifier or JwtVerifier(config, policy)
        self.required_permissions = tuple(
            required_permissions
            if required_permissions is not None
            else config.default_required_permissions
        )

    def _is_public(self, path: str) -> bool:
        for public in self.config.public_paths:
            if path == public or path.startswith(public.rstrip("/") + "/"):
                return True
        return False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path") or "/"
        if self._is_public(path):
            await self.app(scope, receive, send)
            return

        headers = {
            k.decode("latin-1").lower(): v.decode("latin-1")
            for k, v in scope.get("headers", [])
        }
        try:
            token = _extract_bearer_token(headers.get("authorization"))
            principal = self.verifier.verify(token)
            if self.required_permissions:
                self.policy.assert_permissions(
                    principal.effective_permissions,
                    self.required_permissions,
                    require_all=True,
                )
        except (AuthenticationError, AuthorizationError) as exc:
            response = _error_response(exc)
            await response(scope, receive, send)
            return

        # Attach principal for Starlette Request.state
        state = scope.setdefault("state", {})
        if hasattr(state, "__setattr__") and not isinstance(state, dict):
            setattr(state, "principal", principal)
        else:
            state["principal"] = principal  # type: ignore[index]

        await self.app(scope, receive, send)


def require_permission(
    *permissions: str,
    require_all: bool = True,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for route handlers that require specific permissions."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        def _enforce(request: Request) -> JSONResponse | None:
            principal = _get_principal(request)
            if principal is None:
                return _error_response(TokenMissingError("Unauthenticated request"))
            try:
                if "*" in principal.effective_permissions:
                    return None
                if require_all:
                    missing = [
                        p
                        for p in permissions
                        if p not in principal.effective_permissions
                    ]
                    if missing:
                        raise AuthorizationError(
                            f"Missing required permission(s): {', '.join(missing)}"
                        )
                elif not any(p in principal.effective_permissions for p in permissions):
                    raise AuthorizationError(
                        f"Requires one of: {', '.join(permissions)}"
                    )
            except AuthorizationError as exc:
                return _error_response(exc)
            return None

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                request = _find_request(args, kwargs)
                denied = _enforce(request)
                if denied is not None:
                    return denied
                return await func(*args, **kwargs)

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            request = _find_request(args, kwargs)
            denied = _enforce(request)
            if denied is not None:
                return denied
            return func(*args, **kwargs)

        return sync_wrapper

    return decorator


def _find_request(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Request:
    if "request" in kwargs and isinstance(kwargs["request"], Request):
        return kwargs["request"]
    for arg in args:
        if isinstance(arg, Request):
            return arg
    raise TypeError("require_permission expects a Starlette Request argument")
