"""Tests for BiasMonitoringConfig."""

import os
from unittest import mock

import pytest

from model_monitoring.config import BiasMonitoringConfig


class TestBiasMonitoringConfig:
    """Tests for BiasMonitoringConfig class."""

    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        config = BiasMonitoringConfig()

        assert config.bias_threshold == 0.05
        assert config.mlflow_tracking_uri == ""
        assert config.mlflow_registry_uri == ""
        assert config.protected_attributes == [
            "gender",
            "age_group",
            "ethnicity",
            "disability_status",
        ]
        assert config.database_url == ""
        assert config.alert_enabled is True
        assert config.alert_webhook_url == ""

    def test_from_env(self) -> None:
        """Test loading configuration from environment variables."""
        env_vars = {
            "BIAS_THRESHOLD": "0.03",
            "MLFLOW_TRACKING_URI": "http://mlflow:5000",
            "MLFLOW_REGISTRY_URI": "http://mlflow:5000",
            "BIAS_PROTECTED_ATTRIBUTES": "gender,race",
            "BIAS_MONITORING_DATABASE_URL": "postgresql://localhost/test",
            "BIAS_ALERT_ENABLED": "false",
            "BIAS_ALERT_WEBHOOK_URL": "https://hooks.example.com",
        }

        with mock.patch.dict(os.environ, env_vars, clear=False):
            config = BiasMonitoringConfig.from_env()

        assert config.bias_threshold == 0.03
        assert config.mlflow_tracking_uri == "http://mlflow:5000"
        assert config.mlflow_registry_uri == "http://mlflow:5000"
        assert config.protected_attributes == ["gender", "race"]
        assert config.database_url == "postgresql://localhost/test"
        assert config.alert_enabled is False
        assert config.alert_webhook_url == "https://hooks.example.com"

    def test_from_env_with_defaults(self) -> None:
        """Test that from_env uses defaults for missing env vars."""
        with mock.patch.dict(os.environ, {}, clear=True):
            config = BiasMonitoringConfig.from_env()

        assert config.bias_threshold == 0.05
        assert config.protected_attributes == [
            "gender",
            "age_group",
            "ethnicity",
            "disability_status",
        ]

    def test_validate_valid_config(self) -> None:
        """Test that valid configuration passes validation."""
        config = BiasMonitoringConfig(
            bias_threshold=0.05,
            protected_attributes=["gender"],
        )
        config.validate()  # Should not raise

    def test_validate_invalid_threshold_zero(self) -> None:
        """Test that threshold of 0 fails validation."""
        config = BiasMonitoringConfig(bias_threshold=0)

        with pytest.raises(ValueError, match="bias_threshold must be in range"):
            config.validate()

    def test_validate_invalid_threshold_negative(self) -> None:
        """Test that negative threshold fails validation."""
        config = BiasMonitoringConfig(bias_threshold=-0.1)

        with pytest.raises(ValueError, match="bias_threshold must be in range"):
            config.validate()

    def test_validate_invalid_threshold_over_one(self) -> None:
        """Test that threshold > 1 fails validation."""
        config = BiasMonitoringConfig(bias_threshold=1.5)

        with pytest.raises(ValueError, match="bias_threshold must be in range"):
            config.validate()

    def test_validate_empty_protected_attributes(self) -> None:
        """Test that empty protected attributes fails validation."""
        config = BiasMonitoringConfig(protected_attributes=[])

        with pytest.raises(ValueError, match="At least one protected attribute"):
            config.validate()
