"""Service configuration from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ServiceConfig:
    """Configuration for the tenant provisioning service."""

    # Database
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://localhost/asiwdp"
        )
    )

    # Auth
    jwt_issuer: str = field(
        default_factory=lambda: os.getenv("JWT_ISSUER", "https://auth.asiwdp.example")
    )
    jwt_audience: str = field(
        default_factory=lambda: os.getenv("JWT_AUDIENCE", "asiwdp-api")
    )
    jwks_url: str = field(
        default_factory=lambda: os.getenv(
            "JWKS_URL",
            "https://auth.asiwdp.example/.well-known/jwks.json"
        )
    )

    # RBAC matrix path
    rbac_matrix_path: Path = field(
        default_factory=lambda: Path(
            os.getenv(
                "RBAC_MATRIX_PATH",
                str(Path(__file__).parent.parent.parent.parent.parent.parent
                    / "config" / "rbac" / "role-permission-matrix.yaml")
            )
        )
    )

    # Event bus
    event_bus_url: str = field(
        default_factory=lambda: os.getenv("EVENT_BUS_URL", "http://localhost:8080/events")
    )

    # Idempotency
    idempotency_ttl_hours: int = field(
        default_factory=lambda: int(os.getenv("IDEMPOTENCY_TTL_HOURS", "24"))
    )

    # Server
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    debug: bool = field(
        default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true"
    )

    @classmethod
    def from_env(cls) -> ServiceConfig:
        """Load configuration from environment variables."""
        return cls()
