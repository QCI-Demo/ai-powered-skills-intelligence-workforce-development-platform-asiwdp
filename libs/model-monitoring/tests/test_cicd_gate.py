"""Tests for CI/CD gate integration."""

from datetime import datetime, timezone
from unittest import mock
from uuid import uuid4

import pytest

from model_monitoring.bias_evaluator import BiasEvaluationResult
from model_monitoring.cicd_gate import GateResult, check_model_promotion_gate
from model_monitoring.config import BiasMonitoringConfig


@pytest.fixture
def config() -> BiasMonitoringConfig:
    """Create test configuration."""
    return BiasMonitoringConfig(
        bias_threshold=0.05,
        database_url="postgresql://test:test@localhost/test",
    )


class TestGateResult:
    """Tests for GateResult dataclass."""

    def test_to_dict_passed(self) -> None:
        """Test GateResult.to_dict() for passed gate."""
        result = GateResult(
            passed=True,
            model_name="test-model",
            model_version="1",
            bias_index=0.03,
            threshold=0.05,
            message="Model passed",
            details={"evaluation_id": "abc123"},
        )

        d = result.to_dict()
        assert d["passed"] is True
        assert d["model_name"] == "test-model"
        assert d["model_version"] == "1"
        assert d["bias_index"] == 0.03
        assert d["threshold"] == 0.05
        assert d["message"] == "Model passed"
        assert d["details"] == {"evaluation_id": "abc123"}

    def test_to_dict_failed(self) -> None:
        """Test GateResult.to_dict() for failed gate."""
        result = GateResult(
            passed=False,
            model_name="test-model",
            model_version="2",
            bias_index=0.08,
            threshold=0.05,
            message="Model failed",
        )

        d = result.to_dict()
        assert d["passed"] is False
        assert d["bias_index"] == 0.08
        assert d["details"] is None


class TestCheckModelPromotionGate:
    """Tests for check_model_promotion_gate function."""

    def test_no_evaluation_found(self, config: BiasMonitoringConfig) -> None:
        """Test gate when no evaluation exists."""
        with mock.patch(
            "model_monitoring.cicd_gate.BiasMetricsRepository"
        ) as mock_repo:
            mock_repo.return_value.get_latest_evaluation.return_value = None

            result = check_model_promotion_gate("my-model", "1", config)

        assert result.passed is False
        assert result.bias_index == -1.0
        assert "No bias evaluation found" in result.message

    def test_evaluation_passed(self, config: BiasMonitoringConfig) -> None:
        """Test gate when evaluation passes threshold."""
        eval_result = BiasEvaluationResult(
            evaluation_id=uuid4(),
            model_name="my-model",
            model_version="1",
            timestamp=datetime.now(timezone.utc),
            bias_index=0.03,
            threshold_breached=False,
            fairness_metrics=[],
            overall_accuracy=0.9,
        )

        with mock.patch(
            "model_monitoring.cicd_gate.BiasMetricsRepository"
        ) as mock_repo:
            mock_repo.return_value.get_latest_evaluation.return_value = eval_result

            result = check_model_promotion_gate("my-model", "1", config)

        assert result.passed is True
        assert result.bias_index == 0.03
        assert "PASSED" in result.message

    def test_evaluation_failed(self, config: BiasMonitoringConfig) -> None:
        """Test gate when evaluation exceeds threshold."""
        eval_result = BiasEvaluationResult(
            evaluation_id=uuid4(),
            model_name="my-model",
            model_version="1",
            timestamp=datetime.now(timezone.utc),
            bias_index=0.08,
            threshold_breached=True,
            fairness_metrics=[],
            overall_accuracy=0.85,
        )

        with mock.patch(
            "model_monitoring.cicd_gate.BiasMetricsRepository"
        ) as mock_repo:
            mock_repo.return_value.get_latest_evaluation.return_value = eval_result

            result = check_model_promotion_gate("my-model", "1", config)

        assert result.passed is False
        assert result.bias_index == 0.08
        assert "FAILED" in result.message
        assert result.details is not None
