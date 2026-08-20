"""CI/CD integration for bias evaluation gating.

Provides functions to check bias evaluation results and gate model
promotion in CI/CD pipelines.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from typing import List, Optional

from model_monitoring.bias_evaluator import BiasEvaluationResult, BiasEvaluator
from model_monitoring.config import BiasMonitoringConfig
from model_monitoring.db import BiasMetricsRepository

logger = logging.getLogger(__name__)


@dataclass
class GateResult:
    """Result of a promotion gate check.

    Attributes:
        passed: Whether the gate check passed.
        model_name: Name of the evaluated model.
        model_version: Version of the evaluated model.
        bias_index: Computed bias index.
        threshold: Configured bias threshold.
        message: Human-readable result message.
        details: Additional details for logging.
    """

    passed: bool
    model_name: str
    model_version: str
    bias_index: float
    threshold: float
    message: str
    details: Optional[dict] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON output."""
        return {
            "passed": self.passed,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "bias_index": self.bias_index,
            "threshold": self.threshold,
            "message": self.message,
            "details": self.details,
        }


def check_model_promotion_gate(
    model_name: str,
    model_version: str,
    config: Optional[BiasMonitoringConfig] = None,
) -> GateResult:
    """Check if a model passes the bias gate for promotion.

    This function retrieves the latest bias evaluation result for the
    specified model and determines if it meets the threshold requirements
    for promotion.

    Args:
        model_name: Name of the model to check.
        model_version: Version of the model to check.
        config: Optional configuration (defaults to env-based config).

    Returns:
        GateResult indicating pass/fail status.
    """
    if config is None:
        config = BiasMonitoringConfig.from_env()

    repository = BiasMetricsRepository(config)

    result = repository.get_latest_evaluation(model_name, model_version)

    if result is None:
        return GateResult(
            passed=False,
            model_name=model_name,
            model_version=model_version,
            bias_index=-1.0,
            threshold=config.bias_threshold,
            message=(
                f"No bias evaluation found for {model_name} v{model_version}. "
                f"Run bias evaluation before promoting."
            ),
        )

    if result.threshold_breached:
        return GateResult(
            passed=False,
            model_name=model_name,
            model_version=model_version,
            bias_index=result.bias_index,
            threshold=config.bias_threshold,
            message=(
                f"Model {model_name} v{model_version} FAILED bias gate: "
                f"bias_index={result.bias_index:.4f} > threshold={config.bias_threshold}"
            ),
            details={
                "evaluation_id": str(result.evaluation_id),
                "timestamp": result.timestamp.isoformat(),
                "overall_accuracy": result.overall_accuracy,
            },
        )

    return GateResult(
        passed=True,
        model_name=model_name,
        model_version=model_version,
        bias_index=result.bias_index,
        threshold=config.bias_threshold,
        message=(
            f"Model {model_name} v{model_version} PASSED bias gate: "
            f"bias_index={result.bias_index:.4f} <= threshold={config.bias_threshold}"
        ),
        details={
            "evaluation_id": str(result.evaluation_id),
            "timestamp": result.timestamp.isoformat(),
            "overall_accuracy": result.overall_accuracy,
        },
    )


def check_all_production_models_gate(
    config: Optional[BiasMonitoringConfig] = None,
) -> List[GateResult]:
    """Check bias gates for all production models.

    Args:
        config: Optional configuration.

    Returns:
        List of GateResults for each production model.
    """
    if config is None:
        config = BiasMonitoringConfig.from_env()

    evaluator = BiasEvaluator(config)
    models = evaluator.fetch_production_models()

    results = []
    for model_name, model_version, _ in models:
        result = check_model_promotion_gate(model_name, model_version, config)
        results.append(result)

    return results


def main() -> int:
    """CLI entry point for CI/CD bias gate check.

    Usage:
        python -m model_monitoring.cicd_gate <model_name> <model_version>

    Returns:
        0 if gate passed, 1 if failed.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Check bias gate for model promotion"
    )
    parser.add_argument("model_name", help="Name of the model to check")
    parser.add_argument("model_version", help="Version of the model to check")
    parser.add_argument(
        "--output-json",
        action="store_true",
        help="Output result as JSON",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    result = check_model_promotion_gate(args.model_name, args.model_version)

    if args.output_json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(result.message)

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
