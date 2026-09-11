"""API version resolution and ``X-API-Version`` response header middleware."""

from __future__ import annotations

import re
from typing import Iterable

from starlette.types import ASGIApp, Message, Receive, Scope, Send

API_VERSION_HEADER = "X-API-Version"
_VERSION_PATH_RE = re.compile(r"^/api/(v\d+)(?:/|$)", re.IGNORECASE)


def resolve_api_version(
    path: str,
    *,
    request_header: str | None = None,
    default: str = "v1",
    supported: Iterable[str] = ("v1", "v2"),
) -> str:
    """Resolve the active API version from path prefix or request header.

    Path prefixes (``/api/v1/...``, ``/api/v2/...``) take precedence. When the
    path is unversioned, an optional ``X-API-Version`` request header is used.
    Unknown versions fall back to ``default`` when present in ``supported``.
    """
    supported_set = {v.lower() for v in supported}
    match = _VERSION_PATH_RE.match(path or "/")
    if match:
        candidate = match.group(1).lower()
        if candidate in supported_set:
            return candidate

    if request_header:
        header_version = request_header.strip().lower()
        if header_version.startswith("v") and header_version in supported_set:
            return header_version
        # Accept bare major versions ("1", "2")
        bare = f"v{header_version}" if header_version.isdigit() else header_version
        if bare in supported_set:
            return bare

    default_norm = default.lower()
    if default_norm in supported_set:
        return default_norm
    return sorted(supported_set)[0] if supported_set else "v1"


class ApiVersionMiddleware:
    """ASGI middleware that stamps ``X-API-Version`` on every HTTP response.

    Also attaches ``scope['state'].api_version`` for downstream handlers and
    controllers.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        default_version: str = "v1",
        supported_versions: Iterable[str] = ("v1", "v2"),
        header_name: str = API_VERSION_HEADER,
    ) -> None:
        self.app = app
        self.default_version = default_version
        self.supported_versions = tuple(supported_versions)
        self.header_name = header_name

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path") or "/"
        headers = {
            k.decode("latin-1").lower(): v.decode("latin-1")
            for k, v in scope.get("headers", [])
        }
        version = resolve_api_version(
            path,
            request_header=headers.get(self.header_name.lower()),
            default=self.default_version,
            supported=self.supported_versions,
        )

        state = scope.setdefault("state", {})
        if hasattr(state, "__setattr__") and not isinstance(state, dict):
            setattr(state, "api_version", version)
        else:
            state["api_version"] = version  # type: ignore[index]

        header_bytes = self.header_name.encode("latin-1")
        version_bytes = version.encode("latin-1")

        async def send_with_version(message: Message) -> None:
            if message["type"] == "http.response.start":
                raw_headers = list(message.get("headers") or [])
                # Replace any existing X-API-Version to avoid duplicates
                filtered = [
                    (k, v)
                    for k, v in raw_headers
                    if k.decode("latin-1").lower() != self.header_name.lower()
                ]
                filtered.append((header_bytes, version_bytes))
                message = {**message, "headers": filtered}
            await send(message)

        await self.app(scope, receive, send_with_version)
