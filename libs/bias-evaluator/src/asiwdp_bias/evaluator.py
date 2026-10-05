"""Main bias evaluator orchestrating model evaluation pipeline."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional, Union

import numpy as np
import pandas as pd

from asiwdp_bias.config import BiasConfig
from asiwdp_bias.metrics import FairnessMetrics
from asiwdp_bias.models import (
    AttributeEvaluation,
    BiasEvaluationResult,
    ModelEndpoint,
)
from asiwdp_bias.registry import MLflowModelRegistry
from asiwdp_bias.storage import BiasResultStorage

logger = logging.getLogger(__name__)


class BiasEvaluator:
    """Main orchestrator for bias and fairness evaluation of ML models.
    
    This class coordinates:
    1. Fetching model endpoints from MLflow registry
    2. Loading validation data with protected attributes
    3. Running inference and computing fairness metrics
    4. Storing results to PostgreSQL monitoring table
    """

    def __init__(
        self,
        config: BiasConfig,
        registry: Optional[MLflowModelRegistry] = None,
        storage: Optional[BiasResultStorage] = None,
        metrics: Optional[FairnessMetrics] = None,
    ):
        """Initialize the bias evaluator.
        
        Args:
            config: BiasConfig with all settings
            registry: Optional MLflowModelRegistry (created if not provided)
            storage: Optional BiasResultStorage (created if not provided)
            metrics: Optional FairnessMetrics calculator (created if not provided)
        """
        self.config = config
        self.registry = registry or MLflowModelRegistry(config)
        self.storage = storage or BiasResultStorage(config)
        self.metrics = metrics or FairnessMetrics(
            demographic_parity_weight=config.demographic_parity_weight,
            equal_opportunity_weight=config.equal_opportunity_weight,
            equalized_odds_weight=config.equalized_odds_weight,
        )

    def load_validation_data(
        self,
        data_path: Union[str, Path],
        target_column: str = "target",
        protected_attributes: Optional[list[str]] = None,
    ) -> tuple[pd.DataFrame, pd.Series, dict[str, pd.Series]]:
        """Load validation dataset with protected attributes.
        
        Args:
            data_path: Path to validation data (parquet, csv, or json)
            target_column: Name of the target/label column
            protected_attributes: List of protected attribute column names
            
        Returns:
            Tuple of (features DataFrame, target Series, dict of protected attribute Series)
        """
        data_path = Path(data_path)
        
        # Load data based on file extension
        if data_path.suffix == ".parquet":
            df = pd.read_parquet(data_path)
        elif data_path.suffix == ".csv":
            df = pd.read_csv(data_path)
        elif data_path.suffix == ".json":
            df = pd.read_json(data_path)
        else:
            raise ValueError(f"Unsupported data format: {data_path.suffix}")
        
        protected_attributes = protected_attributes or self.config.default_protected_attributes
        
        # Validate required columns exist
        if target_column not in df.columns:
            raise ValueError(f"Target column '{target_column}' not found in data")
        
        missing_attrs = [attr for attr in protected_attributes if attr not in df.columns]
        if missing_attrs:
            logger.warning(f"Protected attributes not found in data: {missing_attrs}")
            protected_attributes = [attr for attr in protected_attributes if attr in df.columns]
        
        if not protected_attributes:
            raise ValueError("No protected attributes found in validation data")
        
        # Extract components
        target = df[target_column]
        protected = {attr: df[attr] for attr in protected_attributes}
        features = df.drop(columns=[target_column] + protected_attributes, errors="ignore")
        
        logger.info(
            f"Loaded validation data: {len(df)} samples, "
            f"protected attributes: {protected_attributes}"
        )
        
        return features, target, protected

    def evaluate_model(
        self,
        endpoint: ModelEndpoint,
        features: pd.DataFrame,
        y_true: pd.Series,
        protected_attributes: dict[str, pd.Series],
        tenant_id: Optional[str] = None,
        predict_fn: Optional[Callable] = None,
    ) -> BiasEvaluationResult:
        """Evaluate a single model for bias and fairness.
        
        Args:
            endpoint: ModelEndpoint with model info
            features: Feature DataFrame for inference
            y_true: True labels
            protected_attributes: Dict mapping attribute names to Series
            tenant_id: Optional tenant ID for multi-tenant deployments
            predict_fn: Optional custom prediction function (for testing)
            
        Returns:
            BiasEvaluationResult with all metrics
        """
        logger.info(f"Evaluating model {endpoint.name} version {endpoint.version}")
        
        # Get predictions
        if predict_fn is not None:
            y_pred = predict_fn(features)
        else:
            model = self.registry.load_model(endpoint)
            y_pred = model.predict(features)
        
        # Ensure predictions are binary (threshold at 0.5 for probabilities)
        y_pred = np.asarray(y_pred)
        if y_pred.dtype == np.float64 or y_pred.dtype == np.float32:
            y_pred = (y_pred >= 0.5).astype(int)
        
        y_true_arr = np.asarray(y_true)
        
        # Evaluate each protected attribute
        attribute_evaluations: list[AttributeEvaluation] = []
        for attr_name, attr_values in protected_attributes.items():
            eval_result = self.metrics.evaluate_attribute(
                y_true=y_true_arr,
                y_pred=y_pred,
                protected_attribute=attr_values,
                attribute_name=attr_name,
            )
            attribute_evaluations.append(eval_result)
        
        # Compute overall bias index (max across attributes)
        overall_bias_index = max(ae.bias_index for ae in attribute_evaluations)
        threshold_breached = overall_bias_index > self.config.threshold
        
        result = BiasEvaluationResult(
            model_name=endpoint.name,
            model_version=endpoint.version,
            model_stage=endpoint.stage,
            evaluation_timestamp=datetime.utcnow(),
            overall_bias_index=overall_bias_index,
            threshold=self.config.threshold,
            threshold_breached=threshold_breached,
            attribute_evaluations=attribute_evaluations,
            total_samples=len(y_true),
            protected_attributes=list(protected_attributes.keys()),
            tenant_id=tenant_id,
            run_id=endpoint.run_id,
        )
        
        if threshold_breached:
            logger.warning(
                f"Model {endpoint.name} v{endpoint.version} FAILED fairness check: "
                f"bias_index={overall_bias_index:.4f} > threshold={self.config.threshold}"
            )
        else:
            logger.info(
                f"Model {endpoint.name} v{endpoint.version} passed fairness check: "
                f"bias_index={overall_bias_index:.4f}"
            )
        
        return result

    def evaluate_all_models(
        self,
        validation_data_path: Union[str, Path],
        protected_attributes: Optional[list[str]] = None,
        target_column: str = "target",
        stages: Optional[list[str]] = None,
        model_names: Optional[list[str]] = None,
        tenant_id: Optional[str] = None,
        store_results: bool = True,
    ) -> list[BiasEvaluationResult]:
        """Evaluate all registered models for bias and fairness.
        
        Args:
            validation_data_path: Path to validation data
            protected_attributes: List of protected attribute columns
            target_column: Name of target column
            stages: Filter models by stage (e.g., ["Production", "Staging"])
            model_names: Specific model names to evaluate (None = all)
            tenant_id: Optional tenant ID
            store_results: Whether to store results to database
            
        Returns:
            List of BiasEvaluationResult for all evaluated models
        """
        # Load validation data
        features, y_true, protected = self.load_validation_data(
            data_path=validation_data_path,
            target_column=target_column,
            protected_attributes=protected_attributes,
        )
        
        # Get models to evaluate
        if model_names:
            endpoints = []
            for name in model_names:
                model_endpoints = self.registry.get_model_versions(name, stages=stages)
                endpoints.extend(model_endpoints)
        elif stages:
            endpoints = []
            for stage in stages:
                endpoints.extend(self.registry.get_models_by_stage(stage))
        else:
            # Get all production and staging models by default
            endpoints = self.registry.get_production_models()
            endpoints.extend(self.registry.get_staging_models())
        
        if not endpoints:
            logger.warning("No models found to evaluate")
            return []
        
        logger.info(f"Evaluating {len(endpoints)} model endpoints")
        
        # Evaluate each model
        results: list[BiasEvaluationResult] = []
        for endpoint in endpoints:
            try:
                result = self.evaluate_model(
                    endpoint=endpoint,
                    features=features,
                    y_true=y_true,
                    protected_attributes=protected,
                    tenant_id=tenant_id,
                )
                results.append(result)
                
                if store_results:
                    self.storage.store_result(result)
                    
            except Exception as e:
                logger.error(
                    f"Failed to evaluate model {endpoint.name} v{endpoint.version}: {e}"
                )
                continue
        
        # Summary logging
        passed = sum(1 for r in results if not r.threshold_breached)
        failed = len(results) - passed
        logger.info(
            f"Evaluation complete: {passed} passed, {failed} failed "
            f"(threshold: {self.config.threshold})"
        )
        
        return results

    def check_model_promotion_gate(
        self,
        model_name: str,
        model_version: str,
        validation_data_path: Union[str, Path],
        protected_attributes: Optional[list[str]] = None,
        target_column: str = "target",
        tenant_id: Optional[str] = None,
    ) -> tuple[bool, BiasEvaluationResult]:
        """Check if a model passes fairness gate for promotion.
        
        This method is intended for CI/CD pipeline integration to gate
        model promotion based on fairness criteria.
        
        Args:
            model_name: Name of model to check
            model_version: Version to check
            validation_data_path: Path to validation data
            protected_attributes: Protected attribute columns
            target_column: Target column name
            tenant_id: Optional tenant ID
            
        Returns:
            Tuple of (passed: bool, result: BiasEvaluationResult)
        """
        # Load data
        features, y_true, protected = self.load_validation_data(
            data_path=validation_data_path,
            target_column=target_column,
            protected_attributes=protected_attributes,
        )
        
        # Get specific model version
        endpoint = self.registry.get_latest_version(model_name)
        if endpoint is None or endpoint.version != model_version:
            # Try to get specific version
            versions = self.registry.get_model_versions(model_name)
            endpoint = next(
                (v for v in versions if v.version == model_version),
                None
            )
        
        if endpoint is None:
            raise ValueError(f"Model {model_name} version {model_version} not found")
        
        # Evaluate
        result = self.evaluate_model(
            endpoint=endpoint,
            features=features,
            y_true=y_true,
            protected_attributes=protected,
            tenant_id=tenant_id,
        )
        
        # Store result
        self.storage.store_result(result)
        
        return result.is_passing(), result

    def generate_report(
        self,
        result: BiasEvaluationResult,
        output_format: str = "text",
    ) -> str:
        """Generate a human-readable bias evaluation report.
        
        Args:
            result: BiasEvaluationResult to report on
            output_format: Output format ("text" or "markdown")
            
        Returns:
            Formatted report string
        """
        if output_format == "markdown":
            return self._generate_markdown_report(result)
        return self._generate_text_report(result)

    def _generate_text_report(self, result: BiasEvaluationResult) -> str:
        """Generate plain text report."""
        lines = [
            "=" * 60,
            "BIAS EVALUATION REPORT",
            "=" * 60,
            f"Model: {result.model_name} (v{result.model_version})",
            f"Stage: {result.model_stage or 'N/A'}",
            f"Timestamp: {result.evaluation_timestamp.isoformat()}",
            f"Samples: {result.total_samples}",
            "",
            "-" * 60,
            "OVERALL RESULTS",
            "-" * 60,
            f"Bias Index: {result.overall_bias_index:.4f}",
            f"Threshold: {result.threshold:.4f}",
            f"Status: {'FAILED' if result.threshold_breached else 'PASSED'}",
            "",
        ]
        
        for attr_eval in result.attribute_evaluations:
            eo_diff = f"{attr_eval.equal_opportunity_diff:.4f}" if attr_eval.equal_opportunity_diff is not None else "N/A"
            eq_odds = f"{attr_eval.equalized_odds_diff:.4f}" if attr_eval.equalized_odds_diff is not None else "N/A"
            lines.extend([
                "-" * 60,
                f"Protected Attribute: {attr_eval.attribute_name}",
                "-" * 60,
                f"  Demographic Parity Diff: {attr_eval.demographic_parity_diff:.4f}",
                f"  Equal Opportunity Diff: {eo_diff}",
                f"  Equalized Odds Diff: {eq_odds}",
                f"  Bias Index: {attr_eval.bias_index:.4f}",
                "",
                "  Group Metrics:",
            ])
            for gm in attr_eval.group_metrics:
                tpr_str = f"{gm.true_positive_rate:.3f}" if gm.true_positive_rate is not None else "N/A"
                lines.append(
                    f"    {gm.group_name}: n={gm.sample_count}, "
                    f"pos_rate={gm.positive_rate:.3f}, "
                    f"TPR={tpr_str}"
                )
            lines.append("")
        
        lines.append("=" * 60)
        return "\n".join(lines)

    def _generate_markdown_report(self, result: BiasEvaluationResult) -> str:
        """Generate markdown report."""
        status_emoji = "❌" if result.threshold_breached else "✅"
        
        lines = [
            "# Bias Evaluation Report",
            "",
            f"**Model:** {result.model_name} (v{result.model_version})",
            f"**Stage:** {result.model_stage or 'N/A'}",
            f"**Timestamp:** {result.evaluation_timestamp.isoformat()}",
            f"**Total Samples:** {result.total_samples:,}",
            "",
            "## Overall Results",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Bias Index | {result.overall_bias_index:.4f} |",
            f"| Threshold | {result.threshold:.4f} |",
            f"| Status | {status_emoji} {'FAILED' if result.threshold_breached else 'PASSED'} |",
            "",
        ]
        
        for attr_eval in result.attribute_evaluations:
            eo_diff = f"{attr_eval.equal_opportunity_diff:.4f}" if attr_eval.equal_opportunity_diff is not None else "N/A"
            eq_odds = f"{attr_eval.equalized_odds_diff:.4f}" if attr_eval.equalized_odds_diff is not None else "N/A"
            lines.extend([
                f"## Protected Attribute: {attr_eval.attribute_name}",
                "",
                "### Fairness Metrics",
                "",
                "| Metric | Value |",
                "|--------|-------|",
                f"| Demographic Parity Diff | {attr_eval.demographic_parity_diff:.4f} |",
                f"| Equal Opportunity Diff | {eo_diff} |",
                f"| Equalized Odds Diff | {eq_odds} |",
                f"| Bias Index | {attr_eval.bias_index:.4f} |",
                "",
                "### Group Breakdown",
                "",
                "| Group | Samples | Pos Rate | TPR | FPR |",
                "|-------|---------|----------|-----|-----|",
            ])
            for gm in attr_eval.group_metrics:
                tpr = f"{gm.true_positive_rate:.3f}" if gm.true_positive_rate is not None else "N/A"
                fpr = f"{gm.false_positive_rate:.3f}" if gm.false_positive_rate is not None else "N/A"
                lines.append(
                    f"| {gm.group_name} | {gm.sample_count:,} | {gm.positive_rate:.3f} | {tpr} | {fpr} |"
                )
            lines.append("")
        
        return "\n".join(lines)
