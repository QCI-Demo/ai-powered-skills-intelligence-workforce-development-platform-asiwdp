"""Tests for configuration module."""

import pytest
from pydantic import SecretStr

from asiwdp_bias.config import BiasConfig, MetricWeights


class TestBiasConfig:
    """Tests for BiasConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = BiasConfig()
        
        assert config.mlflow_tracking_uri == "http://localhost:5000"
        assert config.db_host == "localhost"
        assert config.db_port == 5432
        assert config.db_name == "asiwdp_monitoring"
        assert config.threshold == 0.05
        assert config.demographic_parity_weight == 0.4
        assert config.equal_opportunity_weight == 0.4
        assert config.equalized_odds_weight == 0.2

    def test_threshold_validation(self):
        """Test threshold must be between 0 and 1."""
        with pytest.raises(ValueError):
            BiasConfig(threshold=1.5)
        
        with pytest.raises(ValueError):
            BiasConfig(threshold=-0.1)
        
        # Valid thresholds should work
        config = BiasConfig(threshold=0.0)
        assert config.threshold == 0.0
        
        config = BiasConfig(threshold=1.0)
        assert config.threshold == 1.0

    def test_database_url(self):
        """Test database URL construction."""
        config = BiasConfig(
            db_host="db.example.com",
            db_port=5433,
            db_name="test_db",
            db_user="testuser",
            db_password=SecretStr("testpass"),
        )
        
        expected = "postgresql://testuser:testpass@db.example.com:5433/test_db"
        assert config.database_url == expected

    def test_default_protected_attributes(self):
        """Test default protected attributes."""
        config = BiasConfig()
        
        assert "gender" in config.default_protected_attributes
        assert "age_group" in config.default_protected_attributes
        assert "ethnicity" in config.default_protected_attributes


class TestMetricWeights:
    """Tests for MetricWeights class."""

    def test_valid_weights(self):
        """Test valid weight combinations."""
        weights = MetricWeights(
            demographic_parity=0.4,
            equal_opportunity=0.4,
            equalized_odds=0.2,
        )
        
        assert weights.demographic_parity == 0.4
        assert weights.equal_opportunity == 0.4
        assert weights.equalized_odds == 0.2

    def test_weights_must_sum_to_one(self):
        """Test that weights must sum to 1."""
        with pytest.raises(ValueError, match="sum to 1.0"):
            MetricWeights(
                demographic_parity=0.5,
                equal_opportunity=0.5,
                equalized_odds=0.5,
            )

    def test_default_weights(self):
        """Test default weight values."""
        weights = MetricWeights()
        
        total = (
            weights.demographic_parity
            + weights.equal_opportunity
            + weights.equalized_odds
        )
        assert abs(total - 1.0) < 1e-6
