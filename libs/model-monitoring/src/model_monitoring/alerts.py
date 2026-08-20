"""Alert service for bias threshold breaches.

Sends notifications when bias evaluation detects threshold violations.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any, Dict, List

from model_monitoring.bias_evaluator import BiasEvaluationResult
from model_monitoring.config import BiasMonitoringConfig

logger = logging.getLogger(__name__)


class AlertService:
    """Service for sending bias threshold breach alerts."""

    def __init__(self, config: BiasMonitoringConfig):
        """Initialize the alert service.

        Args:
            config: Bias monitoring configuration.
        """
        self.config = config

    def send_alert(self, result: BiasEvaluationResult) -> bool:
        """Send an alert for a bias threshold breach.

        Args:
            result: The evaluation result that breached threshold.

        Returns:
            True if alert was sent successfully.
        """
        if not self.config.alert_enabled:
            logger.debug("Alerts disabled, skipping")
            return False

        if not self.config.alert_webhook_url:
            logger.warning("Alert webhook URL not configured")
            return False

        if not result.threshold_breached:
            return False

        payload = self._build_alert_payload(result)

        try:
            req = urllib.request.Request(
                self.config.alert_webhook_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                if response.status == 200:
                    logger.info(
                        f"Alert sent for {result.model_name} v{result.model_version}"
                    )
                    return True
                else:
                    logger.error(f"Alert webhook returned status {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            return False

    def send_batch_alerts(
        self, results: List[BiasEvaluationResult]
    ) -> Dict[str, bool]:
        """Send alerts for multiple breached evaluations.

        Args:
            results: List of evaluation results.

        Returns:
            Dict mapping model names to alert success status.
        """
        breached = [r for r in results if r.threshold_breached]
        return {
            f"{r.model_name}:{r.model_version}": self.send_alert(r) for r in breached
        }

    def _build_alert_payload(self, result: BiasEvaluationResult) -> Dict[str, Any]:
        """Build the alert webhook payload.

        Args:
            result: The evaluation result.

        Returns:
            Alert payload dictionary.
        """
        worst_metrics = sorted(
            result.fairness_metrics,
            key=lambda m: m.demographic_parity_diff,
            reverse=True,
        )[:3]

        return {
            "alert_type": "BIAS_THRESHOLD_BREACH",
            "severity": "HIGH" if result.bias_index > 0.1 else "MEDIUM",
            "model_name": result.model_name,
            "model_version": result.model_version,
            "evaluation_id": str(result.evaluation_id),
            "timestamp": result.timestamp.isoformat(),
            "bias_index": result.bias_index,
            "threshold": self.config.bias_threshold,
            "overall_accuracy": result.overall_accuracy,
            "worst_disparities": [
                {
                    "attribute": m.attribute_name,
                    "group": m.group_value,
                    "demographic_parity_diff": m.demographic_parity_diff,
                    "equal_opportunity_diff": m.equal_opportunity_diff,
                }
                for m in worst_metrics
            ],
            "message": (
                f"Model {result.model_name} v{result.model_version} "
                f"exceeded bias threshold: {result.bias_index:.4f} > "
                f"{self.config.bias_threshold}. "
                f"Manual review required before promotion."
            ),
        }
