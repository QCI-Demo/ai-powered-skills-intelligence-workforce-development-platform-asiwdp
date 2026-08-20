"""Model Monitoring Library for Bias and Fairness Evaluation.

This module provides automated fairness and bias monitoring for ML models
served through MLflow. It computes metrics like demographic parity and
equal opportunity, aggregates them into a bias index, and stores results
for audit purposes.
"""

from model_monitoring.bias_evaluator import (
    BiasEvaluator,
    BiasEvaluationResult,
    FairnessMetrics,
)
from model_monitoring.config import BiasMonitoringConfig
from model_monitoring.db import BiasMetricsRepository

__all__ = [
    "BiasEvaluator",
    "BiasEvaluationResult",
    "BiasMonitoringConfig",
    "BiasMetricsRepository",
    "FairnessMetrics",
]

__version__ = "0.1.0"
