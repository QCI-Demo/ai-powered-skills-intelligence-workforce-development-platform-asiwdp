"""Bias evaluation module for ML model fairness monitoring.

This module provides functionality to:
- Fetch model endpoints from MLflow registry
- Load validation data with protected attributes
- Compute fairness metrics (demographic parity, equal opportunity)
- Aggregate metrics into a single bias index
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

import numpy as np
import pandas as pd

from model_monitoring.config import BiasMonitoringConfig

logger = logging.getLogger(__name__)


@dataclass
class FairnessMetrics:
    """Fairness metrics for a protected attribute group.

    Attributes:
        attribute_name: Name of the protected attribute.
        group_value: Specific group value being evaluated.
        sample_size: Number of samples in this group.
        positive_rate: Rate of positive predictions for this group.
        true_positive_rate: True positive rate for this group.
        false_positive_rate: False positive rate for this group.
        demographic_parity_diff: Difference from overall positive rate.
        equal_opportunity_diff: Difference in TPR from reference group.
    """

    attribute_name: str
    group_value: str
    sample_size: int
    positive_rate: float
    true_positive_rate: float
    false_positive_rate: float
    demographic_parity_diff: float = 0.0
    equal_opportunity_diff: float = 0.0


@dataclass
class BiasEvaluationResult:
    """Result of a bias evaluation run.

    Attributes:
        evaluation_id: Unique identifier for this evaluation.
        model_name: Name of the evaluated model.
        model_version: Version of the evaluated model.
        timestamp: When the evaluation was performed.
        bias_index: Aggregated bias index (0-1, lower is better).
        threshold_breached: Whether bias_index exceeds configured threshold.
        fairness_metrics: Per-group fairness metrics.
        overall_accuracy: Model accuracy on validation set.
        metadata: Additional evaluation metadata.
    """

    evaluation_id: UUID
    model_name: str
    model_version: str
    timestamp: datetime
    bias_index: float
    threshold_breached: bool
    fairness_metrics: List[FairnessMetrics]
    overall_accuracy: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class BiasEvaluator:
    """Evaluates ML models for bias and fairness issues.

    This class provides methods to:
    - Fetch models from MLflow registry
    - Run predictions on validation data
    - Compute fairness metrics across protected groups
    - Aggregate into a bias index
    """

    def __init__(self, config: BiasMonitoringConfig):
        """Initialize the bias evaluator.

        Args:
            config: Bias monitoring configuration.
        """
        self.config = config
        self._mlflow_client: Optional[Any] = None

    @property
    def mlflow_client(self) -> Any:
        """Lazily initialize MLflow client."""
        if self._mlflow_client is None:
            try:
                import mlflow

                if self.config.mlflow_tracking_uri:
                    mlflow.set_tracking_uri(self.config.mlflow_tracking_uri)
                if self.config.mlflow_registry_uri:
                    mlflow.set_registry_uri(self.config.mlflow_registry_uri)
                self._mlflow_client = mlflow.MlflowClient()
            except ImportError:
                raise RuntimeError("MLflow is required but not installed")
        return self._mlflow_client

    def fetch_production_models(self) -> List[Tuple[str, str, str]]:
        """Fetch all production-staged models from MLflow registry.

        Returns:
            List of tuples: (model_name, model_version, model_uri)
        """
        models = []
        try:
            for rm in self.mlflow_client.search_registered_models():
                model_name = rm.name
                for mv in self.mlflow_client.search_model_versions(f"name='{model_name}'"):
                    if mv.current_stage == "Production":
                        model_uri = f"models:/{model_name}/{mv.version}"
                        models.append((model_name, mv.version, model_uri))
                        logger.info(f"Found production model: {model_name} v{mv.version}")
        except Exception as e:
            logger.error(f"Error fetching models from MLflow: {e}")
            raise
        return models

    def load_validation_data(
        self,
        data_source: pd.DataFrame | str,
        target_column: str = "target",
    ) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
        """Load validation data with protected attributes.

        Args:
            data_source: DataFrame or path to validation data.
            target_column: Name of the target column.

        Returns:
            Tuple of (features, target, protected_attributes).
        """
        if isinstance(data_source, str):
            if data_source.endswith(".parquet"):
                df = pd.read_parquet(data_source)
            elif data_source.endswith(".csv"):
                df = pd.read_csv(data_source)
            else:
                raise ValueError(f"Unsupported file format: {data_source}")
        else:
            df = data_source.copy()

        available_protected = [
            col for col in self.config.protected_attributes if col in df.columns
        ]
        if not available_protected:
            raise ValueError(
                f"No protected attributes found in data. "
                f"Expected: {self.config.protected_attributes}"
            )

        protected_df = df[available_protected].copy()
        target = df[target_column].copy()
        feature_cols = [
            col
            for col in df.columns
            if col not in available_protected and col != target_column
        ]
        features = df[feature_cols].copy()

        logger.info(
            f"Loaded validation data: {len(df)} samples, "
            f"{len(available_protected)} protected attributes"
        )
        return features, target, protected_df

    def compute_fairness_metrics(
        self,
        y_true: pd.Series | np.ndarray,
        y_pred: np.ndarray,
        protected_attributes: pd.DataFrame,
    ) -> List[FairnessMetrics]:
        """Compute fairness metrics for all protected attribute groups.

        Args:
            y_true: Ground truth labels.
            y_pred: Model predictions.
            protected_attributes: DataFrame of protected attribute values.

        Returns:
            List of FairnessMetrics for each group.
        """
        y_true = np.array(y_true)
        y_pred = np.array(y_pred)

        overall_positive_rate = np.mean(y_pred)
        overall_tpr = self._calculate_tpr(y_true, y_pred)

        metrics = []

        for attr_name in protected_attributes.columns:
            attr_values = protected_attributes[attr_name]
            unique_groups = attr_values.dropna().unique()

            for group_value in unique_groups:
                mask = attr_values == group_value
                group_y_true = y_true[mask]
                group_y_pred = y_pred[mask]

                if len(group_y_pred) == 0:
                    continue

                positive_rate = np.mean(group_y_pred)
                tpr = self._calculate_tpr(group_y_true, group_y_pred)
                fpr = self._calculate_fpr(group_y_true, group_y_pred)

                demographic_parity_diff = abs(positive_rate - overall_positive_rate)
                equal_opportunity_diff = abs(tpr - overall_tpr)

                metrics.append(
                    FairnessMetrics(
                        attribute_name=attr_name,
                        group_value=str(group_value),
                        sample_size=int(mask.sum()),
                        positive_rate=float(positive_rate),
                        true_positive_rate=float(tpr),
                        false_positive_rate=float(fpr),
                        demographic_parity_diff=float(demographic_parity_diff),
                        equal_opportunity_diff=float(equal_opportunity_diff),
                    )
                )

        return metrics

    def calculate_bias_index(self, metrics: List[FairnessMetrics]) -> float:
        """Aggregate fairness metrics into a single bias index.

        The bias index is computed as a weighted combination of:
        - Maximum demographic parity difference across groups
        - Maximum equal opportunity difference across groups
        - Variance in positive rates across groups

        Args:
            metrics: List of FairnessMetrics for all groups.

        Returns:
            Bias index between 0 (no bias) and 1 (maximum bias).
        """
        if not metrics:
            return 0.0

        max_dp_diff = max(m.demographic_parity_diff for m in metrics)
        max_eo_diff = max(m.equal_opportunity_diff for m in metrics)

        positive_rates = [m.positive_rate for m in metrics]
        rate_variance = np.var(positive_rates) if len(positive_rates) > 1 else 0.0

        # Weighted combination (weights sum to 1)
        bias_index = (
            0.4 * min(max_dp_diff, 1.0)
            + 0.4 * min(max_eo_diff, 1.0)
            + 0.2 * min(rate_variance * 4, 1.0)  # Scale variance contribution
        )

        return float(min(bias_index, 1.0))

    def evaluate_model(
        self,
        model_name: str,
        model_version: str,
        model_uri: str,
        validation_data: pd.DataFrame | str,
        target_column: str = "target",
    ) -> BiasEvaluationResult:
        """Run full bias evaluation for a model.

        Args:
            model_name: Name of the model.
            model_version: Version of the model.
            model_uri: MLflow URI to load the model.
            validation_data: Validation data source.
            target_column: Name of target column.

        Returns:
            BiasEvaluationResult with all metrics.
        """
        import mlflow

        logger.info(f"Evaluating model: {model_name} v{model_version}")

        features, y_true, protected_attrs = self.load_validation_data(
            validation_data, target_column
        )

        model = mlflow.pyfunc.load_model(model_uri)
        y_pred = model.predict(features)

        if hasattr(y_pred, "values"):
            y_pred = y_pred.values
        y_pred = np.array(y_pred).flatten()

        if np.issubdtype(y_pred.dtype, np.floating):
            y_pred_binary = (y_pred > 0.5).astype(int)
        else:
            y_pred_binary = y_pred.astype(int)

        fairness_metrics = self.compute_fairness_metrics(
            y_true, y_pred_binary, protected_attrs
        )

        bias_index = self.calculate_bias_index(fairness_metrics)

        accuracy = np.mean(np.array(y_true) == y_pred_binary)

        result = BiasEvaluationResult(
            evaluation_id=uuid4(),
            model_name=model_name,
            model_version=model_version,
            timestamp=datetime.now(timezone.utc),
            bias_index=bias_index,
            threshold_breached=bias_index > self.config.bias_threshold,
            fairness_metrics=fairness_metrics,
            overall_accuracy=float(accuracy),
            metadata={
                "total_samples": len(y_true),
                "protected_attributes": list(protected_attrs.columns),
                "threshold": self.config.bias_threshold,
            },
        )

        if result.threshold_breached:
            logger.warning(
                f"Bias threshold breached for {model_name} v{model_version}: "
                f"{bias_index:.4f} > {self.config.bias_threshold}"
            )
        else:
            logger.info(
                f"Bias evaluation passed for {model_name} v{model_version}: "
                f"{bias_index:.4f} <= {self.config.bias_threshold}"
            )

        return result

    def evaluate_all_production_models(
        self,
        validation_data: pd.DataFrame | str,
        target_column: str = "target",
    ) -> List[BiasEvaluationResult]:
        """Evaluate all production models for bias.

        Args:
            validation_data: Validation data source.
            target_column: Name of target column.

        Returns:
            List of BiasEvaluationResult for each model.
        """
        models = self.fetch_production_models()
        results = []

        for model_name, model_version, model_uri in models:
            try:
                result = self.evaluate_model(
                    model_name=model_name,
                    model_version=model_version,
                    model_uri=model_uri,
                    validation_data=validation_data,
                    target_column=target_column,
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to evaluate {model_name} v{model_version}: {e}")

        return results

    @staticmethod
    def _calculate_tpr(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """Calculate true positive rate."""
        positives = y_true == 1
        if not positives.any():
            return 0.0
        return float(np.mean(y_pred[positives] == 1))

    @staticmethod
    def _calculate_fpr(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """Calculate false positive rate."""
        negatives = y_true == 0
        if not negatives.any():
            return 0.0
        return float(np.mean(y_pred[negatives] == 1))
