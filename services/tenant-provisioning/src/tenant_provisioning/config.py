"""Application configuration."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_prefix="TENANT_PROVISIONING_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Service identity
    service_name: str = "tenant-provisioning"
    service_version: str = "1.0.0"
    environment: str = "development"

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/asiwdp",
        description="PostgreSQL connection string",
    )
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # Server
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False

    # Auth
    jwt_issuer: str = "https://auth.asiwdp.example"
    jwt_audience: str = "asiwdp-api"
    jwt_algorithms: list[str] = ["RS256"]
    jwks_url: str = "https://auth.asiwdp.example/.well-known/jwks.json"
    rbac_matrix_path: str = str(
        Path(__file__).parents[4] / "config" / "rbac" / "role-permission-matrix.yaml"
    )

    # Idempotency
    idempotency_ttl_hours: int = 24

    # Event bus
    event_bus_url: str | None = None
    event_bus_topic: str = "tenant-provisioning-events"

    # Telemetry
    telemetry_enabled: bool = True
    telemetry_endpoint: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
