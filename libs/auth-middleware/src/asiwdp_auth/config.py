"""Auth middleware configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class AuthConfig:
    """Runtime configuration for JWT verification and RBAC."""

    issuer: str
    audience: str | tuple[str, ...]
    # HS256 shared secret OR PEM-encoded public key for RS256
    verification_key: str
    algorithm: str = "HS256"
    leeway_seconds: int = 60
    require_tenant: bool = True
    # Paths that skip authentication (health, docs, openapi)
    public_paths: tuple[str, ...] = (
        "/health",
        "/ready",
        "/live",
        "/docs",
        "/redoc",
        "/openapi.json",
    )
    # Optional default permission required for all protected routes
    default_required_permissions: tuple[str, ...] = field(default_factory=tuple)

    def audiences(self) -> list[str]:
        if isinstance(self.audience, str):
            return [self.audience]
        return list(self.audience)

    @classmethod
    def from_env(cls, *, prefix: str = "ASIWDP_AUTH_") -> AuthConfig:
        """Load config from environment variables.

        Expected variables (prefix default ``ASIWDP_AUTH_``):
        - ``ISSUER``
        - ``AUDIENCE`` (comma-separated for multiple)
        - ``VERIFICATION_KEY`` (secret or PEM public key)
        - ``ALGORITHM`` (default HS256)
        - ``LEEWAY_SECONDS`` (default 60)
        - ``REQUIRE_TENANT`` (default true)
        - ``PUBLIC_PATHS`` (comma-separated, optional)
        """
        issuer = os.environ.get(f"{prefix}ISSUER", "").strip()
        audience_raw = os.environ.get(f"{prefix}AUDIENCE", "").strip()
        key = os.environ.get(f"{prefix}VERIFICATION_KEY", "").strip()
        algorithm = os.environ.get(f"{prefix}ALGORITHM", "HS256").strip() or "HS256"
        leeway = int(os.environ.get(f"{prefix}LEEWAY_SECONDS", "60"))
        require_tenant = (
            os.environ.get(f"{prefix}REQUIRE_TENANT", "true").strip().lower()
            not in {"0", "false", "no"}
        )
        public_raw = os.environ.get(f"{prefix}PUBLIC_PATHS", "").strip()

        if not issuer:
            raise ValueError(f"{prefix}ISSUER is required")
        if not audience_raw:
            raise ValueError(f"{prefix}AUDIENCE is required")
        if not key:
            raise ValueError(f"{prefix}VERIFICATION_KEY is required")

        audiences = tuple(a.strip() for a in audience_raw.split(",") if a.strip())
        default_public = (
            "/health",
            "/ready",
            "/live",
            "/docs",
            "/redoc",
            "/openapi.json",
        )
        public_paths = (
            tuple(p.strip() for p in public_raw.split(",") if p.strip())
            if public_raw
            else default_public
        )

        return cls(
            issuer=issuer,
            audience=audiences if len(audiences) > 1 else audiences[0],
            verification_key=key,
            algorithm=algorithm,
            leeway_seconds=leeway,
            require_tenant=require_tenant,
            public_paths=public_paths,
        )
