"""Tests for data models."""

from datetime import datetime
from uuid import UUID

import pytest

from asiwdp_bias.models import (
    AttributeEvaluation,
    BiasEvaluationResult,
    GroupMetrics,
    ModelEndpoint,
)


class TestGroupMetrics:
    """Tests for GroupMetrics model."""

    def test_basic_creation(self):
        """Test basic GroupMetrics creation."""
        metrics = GroupMetrics(
            group_name="test_group",
            sample_count=100,
            positive_rate=0.5,
        )
        
        assert metrics.group_name == "test_group"
        assert metrics.sample_count == 100
        assert metrics.positive_rate == 0.5

    def test_full_metrics(self):
        """Test GroupMetrics with all fields."""
        metrics = GroupMetrics(
            group_name="male",
            sample_count=500,
            positive_rate=0.6,
            true_positive_rate=0.75,
            false_positive_rate=0.2,
            true_negative_rate=0.8,
            false_negative_rate=0.25,
            precision=0.7,
            accuracy=0.85,
        )
        
        assert metrics.true_positive_rate == 0.75
        assert metrics.false_positive_rate == 0.2
        assert metrics.accuracy == 0.85

    def test_validation_bounds(self):
        """Test that rates are bounded to [0, 1]."""
        with pytest.raises(ValueError):
            GroupMetrics(
                group_name="test",
                sample_count=100,
                positive_rate=1.5,  # Invalid
            )
        
        with pytest.raises(ValueError):
            GroupMetrics(
                group_name="test",
                sample_count=100,
                positive_rate=-0.1,  # Invalid
            )


class TestAttributeEvaluation:
    """Tests for AttributeEvaluation model."""

    def test_basic_creation(self):
        """Test basic AttributeEvaluation creation."""
        attr_eval = AttributeEvaluation(
            attribute_name="gender",
            demographic_parity_diff=0.1,
            bias_index=0.08,
        )
        
        assert attr_eval.attribute_name == "gender"
        assert attr_eval.demographic_parity_diff == 0.1
        assert attr_eval.bias_index == 0.08

    def test_with_group_metrics(self):
        """Test AttributeEvaluation with group metrics."""
        group_metrics = [
            GroupMetrics(group_name="male", sample_count=500, positive_rate=0.6),
            GroupMetrics(group_name="female", sample_count=500, positive_rate=0.5),
        ]
        
        attr_eval = AttributeEvaluation(
            attribute_name="gender",
            group_metrics=group_metrics,
            demographic_parity_diff=0.1,
            equal_opportunity_diff=0.05,
            equalized_odds_diff=0.03,
            bias_index=0.06,
        )
        
        assert len(attr_eval.group_metrics) == 2
        assert attr_eval.equal_opportunity_diff == 0.05


class TestBiasEvaluationResult:
    """Tests for BiasEvaluationResult model."""

    def test_basic_creation(self):
        """Test basic BiasEvaluationResult creation."""
        result = BiasEvaluationResult(
            model_name="test-model",
            model_version="1",
            overall_bias_index=0.03,
            threshold=0.05,
            threshold_breached=False,
            total_samples=1000,
            protected_attributes=["gender"],
        )
        
        assert result.model_name == "test-model"
        assert isinstance(result.id, UUID)
        assert result.is_passing() is True

    def test_threshold_breached(self):
        """Test threshold breach detection."""
        result = BiasEvaluationResult(
            model_name="test-model",
            model_version="1",
            overall_bias_index=0.08,
            threshold=0.05,
            threshold_breached=True,
            total_samples=1000,
            protected_attributes=["gender"],
        )
        
        assert result.is_passing() is False

    def test_get_worst_attribute_empty(self):
        """Test get_worst_attribute with no attributes."""
        result = BiasEvaluationResult(
            model_name="test-model",
            model_version="1",
            overall_bias_index=0.0,
            threshold=0.05,
            threshold_breached=False,
            total_samples=1000,
            protected_attributes=[],
        )
        
        assert result.get_worst_attribute() is None

    def test_get_worst_attribute(self):
        """Test get_worst_attribute returns highest bias."""
        attr_evals = [
            AttributeEvaluation(
                attribute_name="gender",
                demographic_parity_diff=0.1,
                bias_index=0.08,
            ),
            AttributeEvaluation(
                attribute_name="age_group",
                demographic_parity_diff=0.15,
                bias_index=0.12,
            ),
        ]
        
        result = BiasEvaluationResult(
            model_name="test-model",
            model_version="1",
            overall_bias_index=0.12,
            threshold=0.05,
            threshold_breached=True,
            total_samples=1000,
            protected_attributes=["gender", "age_group"],
            attribute_evaluations=attr_evals,
        )
        
        worst = result.get_worst_attribute()
        assert worst.attribute_name == "age_group"
        assert worst.bias_index == 0.12

    def test_evaluation_timestamp_default(self):
        """Test that evaluation timestamp is set by default."""
        result = BiasEvaluationResult(
            model_name="test-model",
            model_version="1",
            overall_bias_index=0.03,
            threshold=0.05,
            threshold_breached=False,
            total_samples=1000,
            protected_attributes=["gender"],
        )
        
        assert result.evaluation_timestamp is not None
        assert isinstance(result.evaluation_timestamp, datetime)


class TestModelEndpoint:
    """Tests for ModelEndpoint model."""

    def test_basic_creation(self):
        """Test basic ModelEndpoint creation."""
        endpoint = ModelEndpoint(
            name="recommendation-ranker",
            version="3",
        )
        
        assert endpoint.name == "recommendation-ranker"
        assert endpoint.version == "3"

    def test_model_uri(self):
        """Test model URI property."""
        endpoint = ModelEndpoint(
            name="recommendation-ranker",
            version="3",
            stage="Production",
        )
        
        assert endpoint.model_uri == "models:/recommendation-ranker/3"

    def test_full_endpoint(self):
        """Test ModelEndpoint with all fields."""
        endpoint = ModelEndpoint(
            name="recommendation-ranker",
            version="3",
            stage="Production",
            run_id="abc123",
            source="s3://models/recommendation-ranker/3",
            description="Test model",
            tags={"team": "ml"},
        )
        
        assert endpoint.run_id == "abc123"
        assert endpoint.tags["team"] == "ml"
