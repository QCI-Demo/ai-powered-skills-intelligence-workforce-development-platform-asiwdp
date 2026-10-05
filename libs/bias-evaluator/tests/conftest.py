"""Test fixtures for bias evaluator tests."""

import numpy as np
import pandas as pd
import pytest

from asiwdp_bias.config import BiasConfig
from asiwdp_bias.metrics import FairnessMetrics
from asiwdp_bias.models import BiasEvaluationResult, GroupMetrics, ModelEndpoint


@pytest.fixture
def config():
    """Test configuration."""
    return BiasConfig(
        mlflow_tracking_uri="http://localhost:5000",
        db_host="localhost",
        db_port=5432,
        db_name="test_asiwdp",
        db_user="test",
        db_password="test",
        threshold=0.05,
    )


@pytest.fixture
def fairness_metrics():
    """Fairness metrics calculator with default weights."""
    return FairnessMetrics(
        demographic_parity_weight=0.4,
        equal_opportunity_weight=0.4,
        equalized_odds_weight=0.2,
    )


@pytest.fixture
def sample_validation_data():
    """Sample validation dataset with protected attributes."""
    np.random.seed(42)
    n = 1000
    
    # Create realistic demographic distribution
    gender = np.random.choice(["male", "female", "other"], n, p=[0.48, 0.48, 0.04])
    age_group = np.random.choice(["18-25", "26-35", "36-45", "46-55", "55+"], n)
    ethnicity = np.random.choice(["group_a", "group_b", "group_c", "group_d"], n)
    
    # Features
    features = pd.DataFrame({
        "feature1": np.random.randn(n),
        "feature2": np.random.randn(n),
        "feature3": np.random.rand(n),
    })
    
    # Create biased target (gender affects outcome)
    base_prob = 0.5
    prob = base_prob + 0.1 * (gender == "male").astype(float)
    target = (np.random.rand(n) < prob).astype(int)
    
    df = features.copy()
    df["gender"] = gender
    df["age_group"] = age_group
    df["ethnicity"] = ethnicity
    df["target"] = target
    
    return df


@pytest.fixture
def unbiased_validation_data():
    """Validation dataset with no demographic bias."""
    np.random.seed(42)
    n = 1000
    
    gender = np.random.choice(["male", "female"], n, p=[0.5, 0.5])
    age_group = np.random.choice(["young", "middle", "senior"], n)
    
    # No bias in target
    target = np.random.choice([0, 1], n, p=[0.5, 0.5])
    
    return pd.DataFrame({
        "feature1": np.random.randn(n),
        "feature2": np.random.randn(n),
        "gender": gender,
        "age_group": age_group,
        "target": target,
    })


@pytest.fixture
def sample_model_endpoint():
    """Sample MLflow model endpoint."""
    return ModelEndpoint(
        name="recommendation-ranker",
        version="3",
        stage="Production",
        run_id="abc123",
        source="s3://models/recommendation-ranker/3",
        description="Recommendation ranking model",
        tags={"team": "ml-platform"},
    )


@pytest.fixture
def sample_group_metrics():
    """Sample group metrics for testing."""
    return [
        GroupMetrics(
            group_name="male",
            sample_count=500,
            positive_rate=0.6,
            true_positive_rate=0.75,
            false_positive_rate=0.2,
        ),
        GroupMetrics(
            group_name="female",
            sample_count=480,
            positive_rate=0.4,
            true_positive_rate=0.65,
            false_positive_rate=0.15,
        ),
        GroupMetrics(
            group_name="other",
            sample_count=20,
            positive_rate=0.5,
            true_positive_rate=0.70,
            false_positive_rate=0.18,
        ),
    ]
