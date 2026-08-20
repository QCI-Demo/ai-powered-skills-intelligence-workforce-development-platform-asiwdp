"""Tests for AlertService."""

import json
from datetime import datetime, timezone
from unittest import mock
from uuid import uuid4

import pytest

from model_monitoring.alerts import AlertService
from model_monitoring.bias_evaluator import BiasEvaluationResult, FairnessMetrics
from model_monitoring.config import BiasMonitoringConfig


@pytest.fixture
def config() -> BiasMonitoringConfig:
    """Create test configuration with alerts enabled."""
    return BiasMonitoringConfig(
        bias_threshold=0.05,
        alert_enabled=True,
        alert_webhook_url="https://hooks.example.com/alert",
    )


@pytest.fixture
def breached_result() -> BiasEvaluationResult:
    """Create a result that breached the threshold."""
    return BiasEvaluationResult(
        evaluation_id=uuid4(),
        model_name="test-model",
        model_version="1",
        timestamp=datetime.now(timezone.utc),
        bias_index=0.08,
        threshold_breached=True,
        fairness_metrics=[
            FairnessMetrics(
                attribute_name="gender",
                group_value="M",
                sample_size=500,
                positive_rate=0.7,
                true_positive_rate=0.9,
                false_positive_rate=0.1,
                demographic_parity_diff=0.2,
                equal_opportunity_diff=0.1,
            ),
            FairnessMetrics(
                attribute_name="gender",
                group_value="F",
                sample_size=500,
                positive_rate=0.5,
                true_positive_rate=0.8,
                false_positive_rate=0.15,
                demographic_parity_diff=0.0,
                equal_opportunity_diff=0.0,
            ),
        ],
        overall_accuracy=0.85,
    )


class TestAlertService:
    """Tests for AlertService class."""

    def test_send_alert_disabled(self, breached_result: BiasEvaluationResult) -> None:
        """Test that alerts are skipped when disabled."""
        config = BiasMonitoringConfig(alert_enabled=False)
        service = AlertService(config)

        result = service.send_alert(breached_result)
        assert result is False

    def test_send_alert_no_webhook(self, breached_result: BiasEvaluationResult) -> None:
        """Test that alerts fail gracefully without webhook URL."""
        config = BiasMonitoringConfig(alert_enabled=True, alert_webhook_url="")
        service = AlertService(config)

        result = service.send_alert(breached_result)
        assert result is False

    def test_send_alert_not_breached(self, config: BiasMonitoringConfig) -> None:
        """Test that no alert is sent for passing evaluation."""
        passing_result = BiasEvaluationResult(
            evaluation_id=uuid4(),
            model_name="test-model",
            model_version="1",
            timestamp=datetime.now(timezone.utc),
            bias_index=0.03,
            threshold_breached=False,
            fairness_metrics=[],
            overall_accuracy=0.9,
        )

        service = AlertService(config)
        result = service.send_alert(passing_result)
        assert result is False

    def test_send_alert_success(
        self, config: BiasMonitoringConfig, breached_result: BiasEvaluationResult
    ) -> None:
        """Test successful alert sending."""
        service = AlertService(config)

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
            mock_response.__exit__ = mock.MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            result = service.send_alert(breached_result)

        assert result is True
        mock_urlopen.assert_called_once()

    def test_send_alert_failure(
        self, config: BiasMonitoringConfig, breached_result: BiasEvaluationResult
    ) -> None:
        """Test alert sending failure handling."""
        service = AlertService(config)

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = Exception("Network error")

            result = service.send_alert(breached_result)

        assert result is False

    def test_build_alert_payload(
        self, config: BiasMonitoringConfig, breached_result: BiasEvaluationResult
    ) -> None:
        """Test alert payload structure."""
        service = AlertService(config)
        payload = service._build_alert_payload(breached_result)

        assert payload["alert_type"] == "BIAS_THRESHOLD_BREACH"
        assert payload["model_name"] == "test-model"
        assert payload["model_version"] == "1"
        assert payload["bias_index"] == 0.08
        assert payload["threshold"] == 0.05
        assert "worst_disparities" in payload
        assert len(payload["worst_disparities"]) <= 3
        assert "message" in payload

    def test_build_alert_payload_severity(
        self, config: BiasMonitoringConfig
    ) -> None:
        """Test alert severity is set based on bias index."""
        service = AlertService(config)

        # High severity for bias > 0.1
        high_result = BiasEvaluationResult(
            evaluation_id=uuid4(),
            model_name="test",
            model_version="1",
            timestamp=datetime.now(timezone.utc),
            bias_index=0.15,
            threshold_breached=True,
            fairness_metrics=[],
            overall_accuracy=0.8,
        )
        high_payload = service._build_alert_payload(high_result)
        assert high_payload["severity"] == "HIGH"

        # Medium severity for bias <= 0.1
        medium_result = BiasEvaluationResult(
            evaluation_id=uuid4(),
            model_name="test",
            model_version="1",
            timestamp=datetime.now(timezone.utc),
            bias_index=0.08,
            threshold_breached=True,
            fairness_metrics=[],
            overall_accuracy=0.8,
        )
        medium_payload = service._build_alert_payload(medium_result)
        assert medium_payload["severity"] == "MEDIUM"

    def test_send_batch_alerts(
        self, config: BiasMonitoringConfig, breached_result: BiasEvaluationResult
    ) -> None:
        """Test sending batch alerts."""
        passing_result = BiasEvaluationResult(
            evaluation_id=uuid4(),
            model_name="passing-model",
            model_version="1",
            timestamp=datetime.now(timezone.utc),
            bias_index=0.02,
            threshold_breached=False,
            fairness_metrics=[],
            overall_accuracy=0.95,
        )

        service = AlertService(config)

        with mock.patch.object(service, "send_alert", return_value=True) as mock_send:
            results = service.send_batch_alerts([breached_result, passing_result])

        # Only breached result should trigger alert
        assert len(results) == 1
        assert "test-model:1" in results
        mock_send.assert_called_once_with(breached_result)
