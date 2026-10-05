"""Tests for the main bias evaluator."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from asiwdp_bias.config import BiasConfig
from asiwdp_bias.evaluator import BiasEvaluator
from asiwdp_bias.models import ModelEndpoint


class TestBiasEvaluator:
    """Tests for BiasEvaluator class."""

    def test_load_validation_data_parquet(self, config, sample_validation_data):
        """Test loading validation data from parquet."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.parquet"
            sample_validation_data.to_parquet(path, index=False)
            
            evaluator = BiasEvaluator(config)
            features, target, protected = evaluator.load_validation_data(
                data_path=path,
                target_column="target",
                protected_attributes=["gender", "age_group"],
            )
            
            assert len(features) == 1000
            assert len(target) == 1000
            assert "gender" in protected
            assert "age_group" in protected

    def test_load_validation_data_csv(self, config, sample_validation_data):
        """Test loading validation data from CSV."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.csv"
            sample_validation_data.to_csv(path, index=False)
            
            evaluator = BiasEvaluator(config)
            features, target, protected = evaluator.load_validation_data(
                data_path=path,
                target_column="target",
                protected_attributes=["gender"],
            )
            
            assert len(target) == 1000
            assert "gender" in protected

    def test_load_validation_data_missing_target(self, config, sample_validation_data):
        """Test error when target column is missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.parquet"
            sample_validation_data.drop(columns=["target"]).to_parquet(path, index=False)
            
            evaluator = BiasEvaluator(config)
            with pytest.raises(ValueError, match="Target column"):
                evaluator.load_validation_data(
                    data_path=path,
                    target_column="target",
                )

    def test_load_validation_data_missing_protected_attrs(self, config, sample_validation_data):
        """Test warning when protected attributes are missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.parquet"
            sample_validation_data.to_parquet(path, index=False)
            
            evaluator = BiasEvaluator(config)
            features, target, protected = evaluator.load_validation_data(
                data_path=path,
                target_column="target",
                protected_attributes=["gender", "nonexistent_attr"],
            )
            
            # Should only include existing attributes
            assert "gender" in protected
            assert "nonexistent_attr" not in protected

    def test_evaluate_model(self, config, sample_validation_data, sample_model_endpoint):
        """Test evaluating a single model."""
        evaluator = BiasEvaluator(config)
        
        # Extract data components
        features = sample_validation_data[["feature1", "feature2", "feature3"]]
        y_true = sample_validation_data["target"]
        protected = {
            "gender": sample_validation_data["gender"],
            "age_group": sample_validation_data["age_group"],
        }
        
        # Create a mock prediction function
        def mock_predict(X):
            # Return slightly biased predictions
            np.random.seed(42)
            return np.random.choice([0, 1], len(X))
        
        result = evaluator.evaluate_model(
            endpoint=sample_model_endpoint,
            features=features,
            y_true=y_true,
            protected_attributes=protected,
            predict_fn=mock_predict,
        )
        
        assert result.model_name == "recommendation-ranker"
        assert result.model_version == "3"
        assert result.total_samples == 1000
        assert len(result.attribute_evaluations) == 2
        assert 0 <= result.overall_bias_index <= 1

    def test_evaluate_model_probability_output(self, config, sample_validation_data, sample_model_endpoint):
        """Test that probability outputs are thresholded."""
        evaluator = BiasEvaluator(config)
        
        features = sample_validation_data[["feature1", "feature2", "feature3"]]
        y_true = sample_validation_data["target"]
        protected = {"gender": sample_validation_data["gender"]}
        
        # Return probabilities instead of binary
        def mock_predict_proba(X):
            np.random.seed(42)
            return np.random.rand(len(X))
        
        result = evaluator.evaluate_model(
            endpoint=sample_model_endpoint,
            features=features,
            y_true=y_true,
            protected_attributes=protected,
            predict_fn=mock_predict_proba,
        )
        
        # Should still work with probability outputs
        assert result is not None
        assert 0 <= result.overall_bias_index <= 1

    def test_threshold_breach_detection(self, config, sample_model_endpoint):
        """Test that threshold breaches are detected."""
        config.threshold = 0.01  # Very strict threshold
        evaluator = BiasEvaluator(config)
        
        # Create highly biased data
        n = 100
        gender = np.array(["male"] * 50 + ["female"] * 50)
        y_true = np.zeros(n)
        y_true[:50] = 1  # All males are positive
        features = pd.DataFrame({"f1": np.random.randn(n)})
        protected = {"gender": pd.Series(gender)}
        
        def biased_predict(X):
            # Predict positive only for first 50 (males)
            return np.array([1] * 50 + [0] * 50)
        
        result = evaluator.evaluate_model(
            endpoint=sample_model_endpoint,
            features=features,
            y_true=pd.Series(y_true),
            protected_attributes=protected,
            predict_fn=biased_predict,
        )
        
        assert result.threshold_breached is True
        assert result.overall_bias_index > config.threshold

    def test_generate_text_report(self, config, sample_validation_data, sample_model_endpoint):
        """Test text report generation."""
        evaluator = BiasEvaluator(config)
        
        features = sample_validation_data[["feature1", "feature2", "feature3"]]
        y_true = sample_validation_data["target"]
        protected = {"gender": sample_validation_data["gender"]}
        
        def mock_predict(X):
            np.random.seed(42)
            return np.random.choice([0, 1], len(X))
        
        result = evaluator.evaluate_model(
            endpoint=sample_model_endpoint,
            features=features,
            y_true=y_true,
            protected_attributes=protected,
            predict_fn=mock_predict,
        )
        
        report = evaluator.generate_report(result, output_format="text")
        
        assert "BIAS EVALUATION REPORT" in report
        assert "recommendation-ranker" in report
        assert "Demographic Parity Diff" in report

    def test_generate_markdown_report(self, config, sample_validation_data, sample_model_endpoint):
        """Test markdown report generation."""
        evaluator = BiasEvaluator(config)
        
        features = sample_validation_data[["feature1", "feature2", "feature3"]]
        y_true = sample_validation_data["target"]
        protected = {"gender": sample_validation_data["gender"]}
        
        def mock_predict(X):
            np.random.seed(42)
            return np.random.choice([0, 1], len(X))
        
        result = evaluator.evaluate_model(
            endpoint=sample_model_endpoint,
            features=features,
            y_true=y_true,
            protected_attributes=protected,
            predict_fn=mock_predict,
        )
        
        report = evaluator.generate_report(result, output_format="markdown")
        
        assert "# Bias Evaluation Report" in report
        assert "| Metric | Value |" in report
        assert "recommendation-ranker" in report


class TestBiasEvaluationResult:
    """Tests for BiasEvaluationResult methods."""

    def test_is_passing(self, config, sample_validation_data, sample_model_endpoint):
        """Test is_passing method."""
        evaluator = BiasEvaluator(config)
        
        features = sample_validation_data[["feature1", "feature2", "feature3"]]
        y_true = sample_validation_data["target"]
        protected = {"gender": sample_validation_data["gender"]}
        
        # Random predictions should generally pass loose threshold
        config.threshold = 0.5
        
        def mock_predict(X):
            np.random.seed(42)
            return np.random.choice([0, 1], len(X))
        
        result = evaluator.evaluate_model(
            endpoint=sample_model_endpoint,
            features=features,
            y_true=y_true,
            protected_attributes=protected,
            predict_fn=mock_predict,
        )
        
        assert result.is_passing() == (not result.threshold_breached)

    def test_get_worst_attribute(self, config, sample_validation_data, sample_model_endpoint):
        """Test get_worst_attribute method."""
        evaluator = BiasEvaluator(config)
        
        features = sample_validation_data[["feature1", "feature2", "feature3"]]
        y_true = sample_validation_data["target"]
        protected = {
            "gender": sample_validation_data["gender"],
            "age_group": sample_validation_data["age_group"],
        }
        
        def mock_predict(X):
            np.random.seed(42)
            return np.random.choice([0, 1], len(X))
        
        result = evaluator.evaluate_model(
            endpoint=sample_model_endpoint,
            features=features,
            y_true=y_true,
            protected_attributes=protected,
            predict_fn=mock_predict,
        )
        
        worst = result.get_worst_attribute()
        assert worst is not None
        assert worst.attribute_name in ["gender", "age_group"]
        # Verify it's actually the worst
        for attr_eval in result.attribute_evaluations:
            assert worst.bias_index >= attr_eval.bias_index
