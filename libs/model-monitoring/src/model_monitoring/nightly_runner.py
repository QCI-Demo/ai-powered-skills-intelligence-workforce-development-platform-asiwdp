#!/usr/bin/env python
"""Nightly bias evaluation runner.

This script is designed to run nightly (via cron or scheduler) to:
1. Fetch all production models from MLflow
2. Run bias evaluation against validation data
3. Store results in PostgreSQL
4. Trigger alerts for threshold breaches
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from typing import Optional

from model_monitoring.alerts import AlertService
from model_monitoring.bias_evaluator import BiasEvaluator
from model_monitoring.config import BiasMonitoringConfig
from model_monitoring.db import BiasMetricsRepository

logger = logging.getLogger(__name__)


def run_nightly_evaluation(
    validation_data_path: str,
    target_column: str = "target",
    config: Optional[BiasMonitoringConfig] = None,
    dry_run: bool = False,
) -> dict:
    """Run nightly bias evaluation for all production models.

    Args:
        validation_data_path: Path to validation dataset.
        target_column: Name of target column in validation data.
        config: Optional configuration (defaults to env-based).
        dry_run: If True, don't persist results or send alerts.

    Returns:
        Summary dict with evaluation statistics.
    """
    if config is None:
        config = BiasMonitoringConfig.from_env()

    config.validate()

    evaluator = BiasEvaluator(config)
    repository = BiasMetricsRepository(config)
    alert_service = AlertService(config)

    if not dry_run:
        repository.initialize_schema()

    logger.info("Starting nightly bias evaluation run")
    start_time = datetime.now(timezone.utc)

    results = evaluator.evaluate_all_production_models(
        validation_data=validation_data_path,
        target_column=target_column,
    )

    models_evaluated = len(results)
    models_passed = sum(1 for r in results if not r.threshold_breached)
    models_failed = models_evaluated - models_passed

    if not dry_run:
        for result in results:
            repository.save_evaluation_result(result)
            if result.threshold_breached:
                alert_service.send_alert(result)

    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()

    summary = {
        "run_timestamp": start_time.isoformat(),
        "duration_seconds": duration,
        "models_evaluated": models_evaluated,
        "models_passed": models_passed,
        "models_failed": models_failed,
        "threshold": config.bias_threshold,
        "dry_run": dry_run,
        "results": [
            {
                "model_name": r.model_name,
                "model_version": r.model_version,
                "bias_index": r.bias_index,
                "threshold_breached": r.threshold_breached,
                "overall_accuracy": r.overall_accuracy,
            }
            for r in results
        ],
    }

    log_level = logging.WARNING if models_failed > 0 else logging.INFO
    logger.log(
        log_level,
        f"Nightly evaluation complete: {models_passed}/{models_evaluated} passed, "
        f"{models_failed} breached threshold ({duration:.1f}s)",
    )

    return summary


def main() -> int:
    """CLI entry point for nightly evaluation runner."""
    parser = argparse.ArgumentParser(
        description="Run nightly bias evaluation for all production models"
    )
    parser.add_argument(
        "validation_data",
        help="Path to validation dataset (CSV or Parquet)",
    )
    parser.add_argument(
        "--target-column",
        default="target",
        help="Name of target column (default: target)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run evaluation without persisting results or sending alerts",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        summary = run_nightly_evaluation(
            validation_data_path=args.validation_data,
            target_column=args.target_column,
            dry_run=args.dry_run,
        )

        if summary["models_failed"] > 0:
            logger.warning(
                f"{summary['models_failed']} model(s) failed bias evaluation"
            )
            return 1

        return 0

    except Exception as e:
        logger.exception(f"Nightly evaluation failed: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
