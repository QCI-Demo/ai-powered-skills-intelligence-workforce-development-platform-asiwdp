"""Configuration for bias monitoring framework."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class BiasMonitoringConfig:
    """Configuration for bias evaluation and monitoring.

    Attributes:
        bias_threshold: Maximum acceptable bias index (default 0.05).
        mlflow_tracking_uri: URI for MLflow tracking server.
        mlflow_registry_uri: URI for MLflow model registry.
        protected_attributes: List of protected attribute column names.
        database_url: PostgreSQL connection URL for storing results.
        alert_enabled: Whether to trigger alerts on threshold breach.
        alert_webhook_url: Webhook URL for sending alerts.
    """

    bias_threshold: float = 0.05
    mlflow_tracking_uri: str = ""
    mlflow_registry_uri: str = ""
    protected_attributes: List[str] = field(
        default_factory=lambda: ["gender", "age_group", "ethnicity", "disability_status"]
    )
    database_url: str = ""
    alert_enabled: bool = True
    alert_webhook_url: str = ""

    @classmethod
    def from_env(cls) -> BiasMonitoringConfig:
        """Load configuration from environment variables."""
        protected_attrs_str = os.environ.get(
            "BIAS_PROTECTED_ATTRIBUTES",
            "gender,age_group,ethnicity,disability_status",
        )
        protected_attrs = [a.strip() for a in protected_attrs_str.split(",") if a.strip()]

        return cls(
            bias_threshold=float(os.environ.get("BIAS_THRESHOLD", "0.05")),
            mlflow_tracking_uri=os.environ.get("MLFLOW_TRACKING_URI", ""),
            mlflow_registry_uri=os.environ.get("MLFLOW_REGISTRY_URI", ""),
            protected_attributes=protected_attrs,
            database_url=os.environ.get("BIAS_MONITORING_DATABASE_URL", ""),
            alert_enabled=os.environ.get("BIAS_ALERT_ENABLED", "true").lower() == "true",
            alert_webhook_url=os.environ.get("BIAS_ALERT_WEBHOOK_URL", ""),
        )

    def validate(self) -> None:
        """Validate configuration values.

        Raises:
            ValueError: If configuration is invalid.
        """
        if self.bias_threshold <= 0 or self.bias_threshold > 1:
            raise ValueError("bias_threshold must be in range (0, 1]")
        if not self.protected_attributes:
            raise ValueError("At least one protected attribute must be specified")
