"""Tests for BiasEvaluator class."""

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from model_monitoring.bias_evaluator import (
    BiasEvaluationResult,
    BiasEvaluator,
    FairnessMetrics,
)
from model_monitoring.config import BiasMonitoringConfig


@pytest.fixture
def config() -> BiasMonitoringConfig:
    """Create test configuration."""
    return BiasMonitoringConfig(
        bias_threshold=0.05,
        protected_attributes=["gender", "age_group"],
    )


@pytest.fixture
def evaluator(config: BiasMonitoringConfig) -> BiasEvaluator:
    """Create test evaluator."""
    return BiasEvaluator(config)


@pytest.fixture
def sample_validation_data() -> pd.DataFrame:
    """Create sample validation data."""
    np.random.seed(42)
    n_samples = 1000

    return pd.DataFrame({
        "feature_1": np.random.randn(n_samples),
        "feature_2": np.random.randn(n_samples),
        "gender": np.random.choice(["M", "F", "NB"], n_samples, p=[0.45, 0.45, 0.1]),
        "age_group": np.random.choice(["18-30", "31-50", "51+"], n_samples),
        "target": np.random.randint(0, 2, n_samples),
    })


class TestBiasEvaluator:
    """Tests for BiasEvaluator class."""

    def test_init(self, evaluator: BiasEvaluator, config: BiasMonitoringConfig) -> None:
        """Test evaluator initialization."""
        assert evaluator.config == config
        assert evaluator._mlflow_client is None

    def test_load_validation_data_dataframe(
        self, evaluator: BiasEvaluator, sample_validation_data: pd.DataFrame
    ) -> None:
        """Test loading validation data from DataFrame."""
        features, target, protected = evaluator.load_validation_data(
            sample_validation_data, target_column="target"
        )

        assert len(features) == 1000
        assert len(target) == 1000
        assert len(protected) == 1000
        assert list(protected.columns) == ["gender", "age_group"]
        assert "feature_1" in features.columns
        assert "feature_2" in features.columns
        assert "gender" not in features.columns
        assert "target" not in features.columns

    def test_load_validation_data_missing_attributes(
        self, evaluator: BiasEvaluator
    ) -> None:
        """Test error when protected attributes are missing."""
        df = pd.DataFrame({
            "feature_1": [1, 2, 3],
            "target": [0, 1, 0],
        })

        with pytest.raises(ValueError, match="No protected attributes found"):
            evaluator.load_validation_data(df, target_column="target")

    def test_compute_fairness_metrics(self, evaluator: BiasEvaluator) -> None:
        """Test computing fairness metrics."""
        y_true = np.array([1, 1, 0, 0, 1, 1, 0, 0])
        y_pred = np.array([1, 1, 0, 0, 1, 0, 1, 0])
        protected = pd.DataFrame({
            "gender": ["M", "M", "M", "M", "F", "F", "F", "F"],
        })

        metrics = evaluator.compute_fairness_metrics(y_true, y_pred, protected)

        assert len(metrics) == 2  # M and F groups

        m_metric = next(m for m in metrics if m.group_value == "M")
        f_metric = next(m for m in metrics if m.group_value == "F")

        assert m_metric.sample_size == 4
        assert f_metric.sample_size == 4
        assert m_metric.attribute_name == "gender"
        assert f_metric.attribute_name == "gender"

    def test_compute_fairness_metrics_with_bias(self, evaluator: BiasEvaluator) -> None:
        """Test computing fairness metrics with intentional bias."""
        # Group A gets mostly positive predictions, Group B mostly negative
        y_true = np.array([1, 1, 1, 1, 0, 0, 0, 0])
        y_pred = np.array([1, 1, 1, 1, 0, 0, 0, 0])  # Perfect predictions
        protected = pd.DataFrame({
            "gender": ["A", "A", "A", "A", "B", "B", "B", "B"],
        })

        metrics = evaluator.compute_fairness_metrics(y_true, y_pred, protected)

        a_metric = next(m for m in metrics if m.group_value == "A")
        b_metric = next(m for m in metrics if m.group_value == "B")

        # Group A has 100% positive rate, Group B has 0%
        assert a_metric.positive_rate == 1.0
        assert b_metric.positive_rate == 0.0

        # Should show significant demographic parity difference
        assert a_metric.demographic_parity_diff > 0

    def test_calculate_bias_index_no_bias(self, evaluator: BiasEvaluator) -> None:
        """Test bias index calculation with no bias."""
        metrics = [
            FairnessMetrics(
                attribute_name="gender",
                group_value="M",
                sample_size=100,
                positive_rate=0.5,
                true_positive_rate=0.8,
                false_positive_rate=0.1,
                demographic_parity_diff=0.0,
                equal_opportunity_diff=0.0,
            ),
            FairnessMetrics(
                attribute_name="gender",
                group_value="F",
                sample_size=100,
                positive_rate=0.5,
                true_positive_rate=0.8,
                false_positive_rate=0.1,
                demographic_parity_diff=0.0,
                equal_opportunity_diff=0.0,
            ),
        ]

        bias_index = evaluator.calculate_bias_index(metrics)
        assert bias_index == 0.0

    def test_calculate_bias_index_with_bias(self, evaluator: BiasEvaluator) -> None:
        """Test bias index calculation with bias present."""
        metrics = [
            FairnessMetrics(
                attribute_name="gender",
                group_value="M",
                sample_size=100,
                positive_rate=0.7,
                true_positive_rate=0.9,
                false_positive_rate=0.1,
                demographic_parity_diff=0.2,
                equal_opportunity_diff=0.1,
            ),
            FairnessMetrics(
                attribute_name="gender",
                group_value="F",
                sample_size=100,
                positive_rate=0.3,
                true_positive_rate=0.7,
                false_positive_rate=0.2,
                demographic_parity_diff=0.2,
                equal_opportunity_diff=0.1,
            ),
        ]

        bias_index = evaluator.calculate_bias_index(metrics)
        assert 0 < bias_index < 1
        # With dp_diff=0.2 and eo_diff=0.1:
        # 0.4 * 0.2 + 0.4 * 0.1 + 0.2 * variance_component
        assert bias_index > 0.1

    def test_calculate_bias_index_empty_metrics(self, evaluator: BiasEvaluator) -> None:
        """Test bias index calculation with empty metrics."""
        bias_index = evaluator.calculate_bias_index([])
        assert bias_index == 0.0

    def test_calculate_tpr(self) -> None:
        """Test true positive rate calculation."""
        y_true = np.array([1, 1, 1, 1, 0, 0])
        y_pred = np.array([1, 1, 0, 0, 0, 0])

        tpr = BiasEvaluator._calculate_tpr(y_true, y_pred)
        assert tpr == 0.5  # 2 out of 4 positives predicted correctly

    def test_calculate_tpr_no_positives(self) -> None:
        """Test TPR calculation when there are no positive examples."""
        y_true = np.array([0, 0, 0])
        y_pred = np.array([1, 0, 0])

        tpr = BiasEvaluator._calculate_tpr(y_true, y_pred)
        assert tpr == 0.0

    def test_calculate_fpr(self) -> None:
        """Test false positive rate calculation."""
        y_true = np.array([0, 0, 0, 0, 1, 1])
        y_pred = np.array([1, 1, 0, 0, 1, 1])

        fpr = BiasEvaluator._calculate_fpr(y_true, y_pred)
        assert fpr == 0.5  # 2 out of 4 negatives predicted as positive

    def test_calculate_fpr_no_negatives(self) -> None:
        """Test FPR calculation when there are no negative examples."""
        y_true = np.array([1, 1, 1])
        y_pred = np.array([1, 0, 0])

        fpr = BiasEvaluator._calculate_fpr(y_true, y_pred)
        assert fpr == 0.0


class TestFairnessMetrics:
    """Tests for FairnessMetrics dataclass."""

    def test_creation(self) -> None:
        """Test creating FairnessMetrics instance."""
        metric = FairnessMetrics(
            attribute_name="gender",
            group_value="M",
            sample_size=100,
            positive_rate=0.6,
            true_positive_rate=0.8,
            false_positive_rate=0.15,
            demographic_parity_diff=0.1,
            equal_opportunity_diff=0.05,
        )

        assert metric.attribute_name == "gender"
        assert metric.group_value == "M"
        assert metric.sample_size == 100
        assert metric.positive_rate == 0.6
        assert metric.true_positive_rate == 0.8
        assert metric.false_positive_rate == 0.15
        assert metric.demographic_parity_diff == 0.1
        assert metric.equal_opportunity_diff == 0.05


class TestBiasEvaluationResult:
    """Tests for BiasEvaluationResult dataclass."""

    def test_creation(self) -> None:
        """Test creating BiasEvaluationResult instance."""
        from uuid import uuid4

        result = BiasEvaluationResult(
            evaluation_id=uuid4(),
            model_name="test-model",
            model_version="1",
            timestamp=datetime.now(timezone.utc),
            bias_index=0.03,
            threshold_breached=False,
            fairness_metrics=[],
            overall_accuracy=0.85,
            metadata={"test": True},
        )

        assert result.model_name == "test-model"
        assert result.model_version == "1"
        assert result.bias_index == 0.03
        assert result.threshold_breached is False
        assert result.overall_accuracy == 0.85
        assert result.metadata == {"test": True}
