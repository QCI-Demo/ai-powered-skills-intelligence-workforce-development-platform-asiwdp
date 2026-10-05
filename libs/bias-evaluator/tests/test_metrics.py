"""Tests for fairness metrics computation."""

import numpy as np
import pandas as pd
import pytest

from asiwdp_bias.metrics import ConfusionMetrics, FairnessMetrics
from asiwdp_bias.models import GroupMetrics


class TestConfusionMetrics:
    """Tests for ConfusionMetrics class."""

    def test_basic_metrics(self):
        """Test basic confusion matrix metric calculations."""
        cm = ConfusionMetrics(
            true_positives=80,
            true_negatives=70,
            false_positives=20,
            false_negatives=30,
        )
        
        assert cm.total == 200
        assert cm.tpr == pytest.approx(80 / 110)  # 80 / (80 + 30)
        assert cm.fpr == pytest.approx(20 / 90)   # 20 / (70 + 20)
        assert cm.tnr == pytest.approx(70 / 90)
        assert cm.fnr == pytest.approx(30 / 110)
        assert cm.precision == pytest.approx(80 / 100)  # 80 / (80 + 20)
        assert cm.accuracy == pytest.approx(150 / 200)

    def test_edge_case_no_positives(self):
        """Test when there are no actual positives."""
        cm = ConfusionMetrics(
            true_positives=0,
            true_negatives=100,
            false_positives=0,
            false_negatives=0,
        )
        
        assert cm.tpr is None
        assert cm.fnr is None
        assert cm.fpr == 0.0
        assert cm.tnr == 1.0

    def test_edge_case_no_negatives(self):
        """Test when there are no actual negatives."""
        cm = ConfusionMetrics(
            true_positives=100,
            true_negatives=0,
            false_positives=0,
            false_negatives=0,
        )
        
        assert cm.fpr is None
        assert cm.tnr is None
        assert cm.tpr == 1.0


class TestFairnessMetrics:
    """Tests for FairnessMetrics class."""

    def test_init_weights_sum_to_one(self):
        """Test that weights must sum to 1."""
        with pytest.raises(ValueError, match="sum to 1.0"):
            FairnessMetrics(
                demographic_parity_weight=0.5,
                equal_opportunity_weight=0.5,
                equalized_odds_weight=0.5,
            )

    def test_init_valid_weights(self):
        """Test valid weight initialization."""
        fm = FairnessMetrics(
            demographic_parity_weight=0.4,
            equal_opportunity_weight=0.4,
            equalized_odds_weight=0.2,
        )
        assert fm.dp_weight == 0.4
        assert fm.eo_weight == 0.4
        assert fm.eod_weight == 0.2

    def test_compute_group_metrics(self, fairness_metrics):
        """Test computing metrics for a single group."""
        y_true = np.array([1, 1, 0, 0, 1, 0, 1, 0])
        y_pred = np.array([1, 0, 0, 1, 1, 0, 1, 0])
        mask = np.array([True, True, True, True, False, False, False, False])
        
        metrics = fairness_metrics.compute_group_metrics(
            y_true=y_true,
            y_pred=y_pred,
            group_mask=mask,
            group_name="test_group",
        )
        
        assert metrics.group_name == "test_group"
        assert metrics.sample_count == 4
        assert metrics.positive_rate == 0.5  # 2 positives out of 4
        assert metrics.true_positive_rate == pytest.approx(0.5)  # 1/2 actual positives
        assert metrics.false_positive_rate == pytest.approx(0.5)  # 1/2 actual negatives

    def test_compute_group_metrics_empty(self, fairness_metrics):
        """Test computing metrics for empty group."""
        y_true = np.array([1, 0, 1, 0])
        y_pred = np.array([1, 0, 0, 1])
        mask = np.array([False, False, False, False])
        
        metrics = fairness_metrics.compute_group_metrics(
            y_true=y_true,
            y_pred=y_pred,
            group_mask=mask,
            group_name="empty_group",
        )
        
        assert metrics.sample_count == 0
        assert metrics.positive_rate == 0.0

    def test_demographic_parity_difference(self, fairness_metrics, sample_group_metrics):
        """Test demographic parity calculation."""
        dpd = fairness_metrics.compute_demographic_parity_difference(sample_group_metrics)
        # max(0.6, 0.4, 0.5) - min(0.6, 0.4, 0.5) = 0.6 - 0.4 = 0.2
        assert dpd == pytest.approx(0.2)

    def test_demographic_parity_perfect(self, fairness_metrics):
        """Test demographic parity when rates are equal."""
        groups = [
            GroupMetrics(group_name="a", sample_count=100, positive_rate=0.5),
            GroupMetrics(group_name="b", sample_count=100, positive_rate=0.5),
        ]
        dpd = fairness_metrics.compute_demographic_parity_difference(groups)
        assert dpd == pytest.approx(0.0)

    def test_equal_opportunity_difference(self, fairness_metrics, sample_group_metrics):
        """Test equal opportunity calculation."""
        eod = fairness_metrics.compute_equal_opportunity_difference(sample_group_metrics)
        # max(0.75, 0.65, 0.70) - min(0.75, 0.65, 0.70) = 0.75 - 0.65 = 0.1
        assert eod == pytest.approx(0.1)

    def test_equal_opportunity_none_tpr(self, fairness_metrics):
        """Test equal opportunity when TPR is None for some groups."""
        groups = [
            GroupMetrics(group_name="a", sample_count=100, positive_rate=0.5, true_positive_rate=0.8),
            GroupMetrics(group_name="b", sample_count=100, positive_rate=0.5, true_positive_rate=None),
        ]
        eod = fairness_metrics.compute_equal_opportunity_difference(groups)
        assert eod is None

    def test_equalized_odds_difference(self, fairness_metrics, sample_group_metrics):
        """Test equalized odds calculation."""
        eq_odds = fairness_metrics.compute_equalized_odds_difference(sample_group_metrics)
        # TPR diff: 0.75 - 0.65 = 0.1
        # FPR diff: 0.2 - 0.15 = 0.05
        # Average: (0.1 + 0.05) / 2 = 0.075
        assert eq_odds == pytest.approx(0.075)

    def test_bias_index_all_metrics(self, fairness_metrics):
        """Test bias index with all metrics available."""
        bias_index = fairness_metrics.compute_bias_index(
            demographic_parity_diff=0.2,
            equal_opportunity_diff=0.1,
            equalized_odds_diff=0.05,
        )
        # 0.4 * 0.2 + 0.4 * 0.1 + 0.2 * 0.05 = 0.08 + 0.04 + 0.01 = 0.13
        assert bias_index == pytest.approx(0.13)

    def test_bias_index_missing_metrics(self, fairness_metrics):
        """Test bias index with some metrics unavailable."""
        bias_index = fairness_metrics.compute_bias_index(
            demographic_parity_diff=0.2,
            equal_opportunity_diff=None,
            equalized_odds_diff=None,
        )
        # Only demographic parity, so it's weighted at 100%
        assert bias_index == pytest.approx(0.2)

    def test_bias_index_clamped(self, fairness_metrics):
        """Test that bias index is clamped to [0, 1]."""
        bias_index = fairness_metrics.compute_bias_index(
            demographic_parity_diff=1.5,
            equal_opportunity_diff=1.5,
            equalized_odds_diff=1.5,
        )
        assert bias_index == 1.0

    def test_evaluate_attribute(self, fairness_metrics, sample_validation_data):
        """Test full attribute evaluation."""
        y_true = sample_validation_data["target"].values
        # Simulate predictions with some bias
        y_pred = (sample_validation_data["target"].values + 
                  (sample_validation_data["gender"] == "male").astype(int) * 0.1 > 0.5).astype(int)
        
        result = fairness_metrics.evaluate_attribute(
            y_true=y_true,
            y_pred=y_pred,
            protected_attribute=sample_validation_data["gender"],
            attribute_name="gender",
        )
        
        assert result.attribute_name == "gender"
        assert len(result.group_metrics) == 3  # male, female, other
        assert result.demographic_parity_diff >= 0
        assert 0 <= result.bias_index <= 1


class TestEvaluateAttribute:
    """Integration tests for attribute evaluation."""

    def test_unbiased_data(self, fairness_metrics, unbiased_validation_data):
        """Test evaluation on data with no bias."""
        y_true = unbiased_validation_data["target"].values
        # Use random predictions (unbiased)
        np.random.seed(42)
        y_pred = np.random.choice([0, 1], len(y_true))
        
        result = fairness_metrics.evaluate_attribute(
            y_true=y_true,
            y_pred=y_pred,
            protected_attribute=unbiased_validation_data["gender"],
            attribute_name="gender",
        )
        
        # With random data, bias should be relatively low
        # (though not necessarily zero due to random variation)
        assert result.bias_index < 0.3

    def test_highly_biased_data(self, fairness_metrics):
        """Test evaluation on highly biased predictions."""
        n = 1000
        np.random.seed(42)
        
        gender = np.array(["male"] * 500 + ["female"] * 500)
        y_true = np.random.choice([0, 1], n)
        
        # Highly biased predictions: always predict positive for males
        y_pred = np.array([1] * 500 + [0] * 500)
        
        result = fairness_metrics.evaluate_attribute(
            y_true=y_true,
            y_pred=y_pred,
            protected_attribute=pd.Series(gender),
            attribute_name="gender",
        )
        
        # Should show high demographic parity difference (1.0 - 0.0 = 1.0)
        assert result.demographic_parity_diff == pytest.approx(1.0)
        assert result.bias_index > 0.5
