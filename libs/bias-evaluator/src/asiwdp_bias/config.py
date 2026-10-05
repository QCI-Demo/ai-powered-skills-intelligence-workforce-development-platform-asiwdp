"""Configuration for the bias evaluator module."""

from __future__ import annotations

import os
from typing import Optional

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BiasConfig(BaseSettings):
    """Configuration for bias evaluation framework.
    
    Loads settings from environment variables with BIAS_ prefix.
    """

    model_config = SettingsConfigDict(
        env_prefix="BIAS_",
        env_file=".env",
        extra="ignore",
    )

    # MLflow configuration
    mlflow_tracking_uri: str = Field(
        default="http://localhost:5000",
        description="MLflow tracking server URI",
        alias="MLFLOW_TRACKING_URI",
    )
    mlflow_registry_uri: Optional[str] = Field(
        default=None,
        description="MLflow model registry URI (defaults to tracking URI)",
    )

    # PostgreSQL configuration
    db_host: str = Field(default="localhost", description="PostgreSQL host")
    db_port: int = Field(default=5432, description="PostgreSQL port")
    db_name: str = Field(default="asiwdp_monitoring", description="Database name")
    db_user: str = Field(default="", description="Database user")
    db_password: SecretStr = Field(default=SecretStr(""), description="Database password")
    db_schema: str = Field(default="public", description="Database schema")

    # Evaluation configuration
    threshold: float = Field(
        default=0.05,
        ge=0.0,
        le=1.0,
        description="Maximum acceptable bias index (default: 0.05)",
    )
    
    # Metric weights for bias index calculation
    demographic_parity_weight: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Weight for demographic parity in bias index",
    )
    equal_opportunity_weight: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Weight for equal opportunity in bias index",
    )
    equalized_odds_weight: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Weight for equalized odds in bias index",
    )

    # Default protected attributes
    default_protected_attributes: list[str] = Field(
        default_factory=lambda: ["gender", "age_group", "ethnicity"],
        description="Default protected attribute columns",
    )

    @field_validator("threshold")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        """Ensure threshold is within valid range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Threshold must be between 0 and 1")
        return v

    @property
    def database_url(self) -> str:
        """Construct PostgreSQL connection URL."""
        password = self.db_password.get_secret_value()
        return (
            f"postgresql://{self.db_user}:{password}@"
            f"{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @classmethod
    def from_env(cls) -> "BiasConfig":
        """Create config from environment variables."""
        return cls(
            mlflow_tracking_uri=os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"),
        )


class MetricWeights:
    """Weights for combining fairness metrics into bias index."""

    def __init__(
        self,
        demographic_parity: float = 0.4,
        equal_opportunity: float = 0.4,
        equalized_odds: float = 0.2,
    ):
        total = demographic_parity + equal_opportunity + equalized_odds
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Metric weights must sum to 1.0, got {total}")
        self.demographic_parity = demographic_parity
        self.equal_opportunity = equal_opportunity
        self.equalized_odds = equalized_odds
