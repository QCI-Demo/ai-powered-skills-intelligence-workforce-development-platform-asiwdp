"""Service configuration from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ServiceConfig:
    """Configuration for the tenant provisioning service."""

    # Database
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", "postgresql+asyncpg://localhost:5432/asiwdp"
        )
    )

    # Authentication
    auth_issuer: str = field(
        default_factory=lambda: os.getenv("AUTH_ISSUER", "https://auth.asiwdp.example/")
    )
    auth_audience: str = field(
        default_factory=lambda: os.getenv("AUTH_AUDIENCE", "asiwdp-api")
    )
    auth_verification_key: str = field(
        default_factory=lambda: os.getenv("AUTH_VERIFICATION_KEY", "")
    )
    auth_algorithm: str = field(
        default_factory=lambda: os.getenv("AUTH_ALGORITHM", "RS256")
    )
    rbac_matrix_path: Path = field(
        default_factory=lambda: Path(
            os.getenv(
                "RBAC_MATRIX_PATH",
                str(Path(__file__).parents[4] / "config" / "rbac" / "role-permission-matrix.yaml"),
            )
        )
    )

    # Event Bus
    event_bus_url: str = field(
        default_factory=lambda: os.getenv("EVENT_BUS_URL", "")
    )
    event_bus_topic: str = field(
        default_factory=lambda: os.getenv("EVENT_BUS_TOPIC", "tenant-events")
    )

    # Idempotency
    idempotency_ttl_hours: int = field(
        default_factory=lambda: int(os.getenv("IDEMPOTENCY_TTL_HOURS", "24"))
    )

    # Service
    service_name: str = "tenant-provisioning"
    public_paths: tuple[str, ...] = ("/health", "/health/", "/metrics", "/metrics/")

    @classmethod
    def from_env(cls) -> ServiceConfig:
        """Load configuration from environment."""
        return cls()


# Global config instance
config = ServiceConfig.from_env()
