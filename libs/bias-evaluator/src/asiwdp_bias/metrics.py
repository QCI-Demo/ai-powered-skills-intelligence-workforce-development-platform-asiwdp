"""Fairness metrics computation for bias evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from asiwdp_bias.models import AttributeEvaluation, GroupMetrics


@dataclass
class ConfusionMetrics:
    """Confusion matrix derived metrics for a group."""

    true_positives: int
    true_negatives: int
    false_positives: int
    false_negatives: int

    @property
    def total(self) -> int:
        return (
            self.true_positives
            + self.true_negatives
            + self.false_positives
            + self.false_negatives
        )

    @property
    def tpr(self) -> Optional[float]:
        """True Positive Rate (Recall/Sensitivity)."""
        positives = self.true_positives + self.false_negatives
        return self.true_positives / positives if positives > 0 else None

    @property
    def fpr(self) -> Optional[float]:
        """False Positive Rate."""
        negatives = self.true_negatives + self.false_positives
        return self.false_positives / negatives if negatives > 0 else None

    @property
    def tnr(self) -> Optional[float]:
        """True Negative Rate (Specificity)."""
        negatives = self.true_negatives + self.false_positives
        return self.true_negatives / negatives if negatives > 0 else None

    @property
    def fnr(self) -> Optional[float]:
        """False Negative Rate."""
        positives = self.true_positives + self.false_negatives
        return self.false_negatives / positives if positives > 0 else None

    @property
    def precision(self) -> Optional[float]:
        """Precision."""
        predicted_positives = self.true_positives + self.false_positives
        return self.true_positives / predicted_positives if predicted_positives > 0 else None

    @property
    def accuracy(self) -> Optional[float]:
        """Accuracy."""
        return (self.true_positives + self.true_negatives) / self.total if self.total > 0 else None


class FairnessMetrics:
    """Compute fairness metrics across demographic groups."""

    def __init__(
        self,
        demographic_parity_weight: float = 0.4,
        equal_opportunity_weight: float = 0.4,
        equalized_odds_weight: float = 0.2,
    ):
        """Initialize with metric weights for bias index calculation.
        
        Args:
            demographic_parity_weight: Weight for demographic parity difference
            equal_opportunity_weight: Weight for equal opportunity difference
            equalized_odds_weight: Weight for equalized odds difference
        """
        total = demographic_parity_weight + equal_opportunity_weight + equalized_odds_weight
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Weights must sum to 1.0, got {total}")
        
        self.dp_weight = demographic_parity_weight
        self.eo_weight = equal_opportunity_weight
        self.eod_weight = equalized_odds_weight

    def compute_group_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        group_mask: np.ndarray,
        group_name: str,
    ) -> GroupMetrics:
        """Compute metrics for a single demographic group.
        
        Args:
            y_true: True labels (binary)
            y_pred: Predicted labels (binary)
            group_mask: Boolean mask for this group
            group_name: Name/identifier for this group
            
        Returns:
            GroupMetrics instance with computed values
        """
        group_true = y_true[group_mask]
        group_pred = y_pred[group_mask]
        sample_count = len(group_true)

        if sample_count == 0:
            return GroupMetrics(
                group_name=group_name,
                sample_count=0,
                positive_rate=0.0,
            )

        # Positive prediction rate (for demographic parity)
        positive_rate = np.mean(group_pred)

        # Compute confusion metrics if we have ground truth
        cm = self._compute_confusion_metrics(group_true, group_pred)

        return GroupMetrics(
            group_name=group_name,
            sample_count=sample_count,
            positive_rate=float(positive_rate),
            true_positive_rate=cm.tpr,
            false_positive_rate=cm.fpr,
            true_negative_rate=cm.tnr,
            false_negative_rate=cm.fnr,
            precision=cm.precision,
            accuracy=cm.accuracy,
        )

    def _compute_confusion_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
    ) -> ConfusionMetrics:
        """Compute confusion matrix metrics."""
        tp = int(np.sum((y_true == 1) & (y_pred == 1)))
        tn = int(np.sum((y_true == 0) & (y_pred == 0)))
        fp = int(np.sum((y_true == 0) & (y_pred == 1)))
        fn = int(np.sum((y_true == 1) & (y_pred == 0)))
        return ConfusionMetrics(tp, tn, fp, fn)

    def compute_demographic_parity_difference(
        self,
        group_metrics: list[GroupMetrics],
    ) -> float:
        """Compute demographic parity difference.
        
        Demographic parity requires that the positive prediction rate
        is the same across all groups.
        
        DPD = max(P(ŷ=1|G=g)) - min(P(ŷ=1|G=g))
        
        Returns:
            Difference between max and min positive rates (0 = perfect parity)
        """
        rates = [g.positive_rate for g in group_metrics if g.sample_count > 0]
        if len(rates) < 2:
            return 0.0
        return max(rates) - min(rates)

    def compute_equal_opportunity_difference(
        self,
        group_metrics: list[GroupMetrics],
    ) -> Optional[float]:
        """Compute equal opportunity difference.
        
        Equal opportunity requires that the true positive rate
        is the same across all groups (equalized among positive class).
        
        EOD = max(TPR(G=g)) - min(TPR(G=g))
        
        Returns:
            Difference between max and min TPR (0 = perfect equality)
            None if TPR cannot be computed for all groups
        """
        tprs = [
            g.true_positive_rate
            for g in group_metrics
            if g.true_positive_rate is not None and g.sample_count > 0
        ]
        if len(tprs) < 2:
            return None
        return max(tprs) - min(tprs)

    def compute_equalized_odds_difference(
        self,
        group_metrics: list[GroupMetrics],
    ) -> Optional[float]:
        """Compute equalized odds difference.
        
        Equalized odds requires both TPR and FPR to be equal across groups.
        We compute as average of TPR and FPR differences.
        
        Returns:
            Average of TPR and FPR differences (0 = perfect equalized odds)
            None if metrics cannot be computed
        """
        tprs = [
            g.true_positive_rate
            for g in group_metrics
            if g.true_positive_rate is not None and g.sample_count > 0
        ]
        fprs = [
            g.false_positive_rate
            for g in group_metrics
            if g.false_positive_rate is not None and g.sample_count > 0
        ]

        if len(tprs) < 2 or len(fprs) < 2:
            return None

        tpr_diff = max(tprs) - min(tprs)
        fpr_diff = max(fprs) - min(fprs)

        return (tpr_diff + fpr_diff) / 2.0

    def compute_bias_index(
        self,
        demographic_parity_diff: float,
        equal_opportunity_diff: Optional[float],
        equalized_odds_diff: Optional[float],
    ) -> float:
        """Compute aggregated bias index.
        
        Combines multiple fairness metrics into a single index using
        configured weights. If some metrics are unavailable, remaining
        weights are redistributed proportionally.
        
        Args:
            demographic_parity_diff: Demographic parity difference
            equal_opportunity_diff: Equal opportunity difference (optional)
            equalized_odds_diff: Equalized odds difference (optional)
            
        Returns:
            Weighted bias index in range [0, 1]
        """
        metrics = []
        weights = []

        # Always include demographic parity
        metrics.append(demographic_parity_diff)
        weights.append(self.dp_weight)

        if equal_opportunity_diff is not None:
            metrics.append(equal_opportunity_diff)
            weights.append(self.eo_weight)

        if equalized_odds_diff is not None:
            metrics.append(equalized_odds_diff)
            weights.append(self.eod_weight)

        # Normalize weights to sum to 1
        total_weight = sum(weights)
        normalized_weights = [w / total_weight for w in weights]

        # Compute weighted average
        bias_index = sum(m * w for m, w in zip(metrics, normalized_weights))

        # Clamp to [0, 1]
        return max(0.0, min(1.0, bias_index))

    def evaluate_attribute(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        protected_attribute: pd.Series,
        attribute_name: str,
    ) -> AttributeEvaluation:
        """Evaluate fairness for a single protected attribute.
        
        Args:
            y_true: True labels
            y_pred: Predicted labels
            protected_attribute: Series with group values for each sample
            attribute_name: Name of the protected attribute
            
        Returns:
            AttributeEvaluation with all computed metrics
        """
        # Get unique groups
        groups = protected_attribute.dropna().unique()
        group_metrics = []

        for group in groups:
            mask = (protected_attribute == group).values
            metrics = self.compute_group_metrics(
                y_true=y_true,
                y_pred=y_pred,
                group_mask=mask,
                group_name=str(group),
            )
            group_metrics.append(metrics)

        # Compute fairness differences
        dpd = self.compute_demographic_parity_difference(group_metrics)
        eod = self.compute_equal_opportunity_difference(group_metrics)
        eq_odds = self.compute_equalized_odds_difference(group_metrics)

        # Compute bias index
        bias_index = self.compute_bias_index(dpd, eod, eq_odds)

        return AttributeEvaluation(
            attribute_name=attribute_name,
            group_metrics=group_metrics,
            demographic_parity_diff=dpd,
            equal_opportunity_diff=eod,
            equalized_odds_diff=eq_odds,
            bias_index=bias_index,
        )
