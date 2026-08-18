"""Tests for recommendation, career-forecast, and adaptive-sequencing models."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from asiwdp_ml.adaptive_sequencing.predict import AdaptiveSequencingModel
from asiwdp_ml.adaptive_sequencing.train import train_adaptive_sequencing_model
from asiwdp_ml.career_forecast.predict import CareerForecastModel
from asiwdp_ml.career_forecast.train import train_career_forecast_model
from asiwdp_ml.common.feature_store import FeatureStoreClient
from asiwdp_ml.common.metrics import average_precision_at_k, mean_average_precision_at_k
from asiwdp_ml.common.skills_framework import SkillsFrameworkClient
from asiwdp_ml.recommendation.predict import RecommendationModel
from asiwdp_ml.recommendation.train import train_recommendation_model
from asiwdp_ml.serving.app import create_app
from validate_serving_endpoint import sample_payload


@pytest.fixture(scope="module")
def recommendation_artifacts(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("rec")
    result = train_recommendation_model(
        artifact_dir=root, register=False, n_learners=60, seed=1
    )
    assert result["map_at_5"] >= 0.0
    assert (root / "model.joblib").exists()
    assert (root / "metadata.json").exists()
    return root


@pytest.fixture(scope="module")
def career_artifacts(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("career")
    result = train_career_forecast_model(
        artifact_dir=root, register=False, n_learners=120, seed=1
    )
    assert result["accuracy"] >= 0.0
    return root


@pytest.fixture(scope="module")
def sequencing_artifacts(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("seq")
    result = train_adaptive_sequencing_model(
        artifact_dir=root, register=False, n_learners=40, seed=1
    )
    assert "rmse" in result
    return root


def test_feature_store_extracts_recommendation_frame():
    df = FeatureStoreClient(seed=0).extract_recommendation_training_data(n_learners=5)
    assert len(df) > 0
    assert {"skill_gap_mean", "content_relevance", "learner_activity_rate", "label"} <= set(df.columns)
    assert df["learner_id"].str.startswith("learner_").all()


def test_skills_framework_role_transitions():
    client = SkillsFrameworkClient(seed=0)
    transitions = client.fetch_role_transition_matrix()
    assert len(transitions) > 0
    assert {"from_role", "to_role", "transition_rate"} <= set(transitions.columns)


def test_map_at_5_metric():
    ap = average_precision_at_k([1, 0, 1, 0, 0], [0.9, 0.8, 0.7, 0.2, 0.1], k=5)
    assert 0.0 < ap <= 1.0


def test_recommendation_predict_includes_rationale_and_metadata(recommendation_artifacts: Path):
    model = RecommendationModel(recommendation_artifacts)
    payload = sample_payload("recommendation")["candidates"]
    out = model.predict(payload, top_k=2)
    assert out["rationale"]
    assert out["model_metadata"]["model_name"]
    assert out["model_metadata"]["model_version"]
    assert out["predictions"][0]["rationale"]
    assert out["predictions"][0]["rank"] == 1


def test_career_forecast_predict_includes_rationale(career_artifacts: Path):
    model = CareerForecastModel(career_artifacts)
    features = sample_payload("career_forecast")["features"]
    out = model.predict(features, top_k=3)
    assert len(out["predictions"]) == 3
    assert "Predicted next role" in out["rationale"]
    assert out["model_metadata"]["framework"]


def test_adaptive_sequencing_orders_modules(sequencing_artifacts: Path):
    model = AdaptiveSequencingModel(sequencing_artifacts)
    modules = sample_payload("adaptive_sequencing")["modules"]
    out = model.predict(modules)
    positions = [p["position"] for p in out["predictions"]]
    assert positions == [1, 2, 3]
    assert all(p["rationale"] for p in out["predictions"])
    assert out["model_metadata"]["model_version"]


def test_recommendation_serving_endpoint(recommendation_artifacts: Path):
    app = create_app("recommendation", recommendation_artifacts)
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["model_metadata"]["model_version"]
        resp = client.post("/predict", json=sample_payload("recommendation"))
        assert resp.status_code == 200
        body = resp.json()
        assert body["rationale"]
        assert body["model_metadata"]["model_name"] == json.loads(
            (recommendation_artifacts / "metadata.json").read_text()
        )["model_name"]
        # Versioned alias routes
        v1_health = client.get("/api/v1/health")
        assert v1_health.status_code == 200
        v1_resp = client.post("/api/v1/predict", json=sample_payload("recommendation"))
        assert v1_resp.status_code == 200
        assert v1_resp.json()["model_metadata"]["model_version"]


def test_career_serving_endpoint(career_artifacts: Path):
    app = create_app("career_forecast", career_artifacts)
    with TestClient(app) as client:
        resp = client.post("/predict", json=sample_payload("career_forecast"))
        assert resp.status_code == 200
        assert resp.json()["model_metadata"]["model_version"]


def test_sequencing_serving_endpoint(sequencing_artifacts: Path):
    app = create_app("adaptive_sequencing", sequencing_artifacts)
    with TestClient(app) as client:
        resp = client.post("/predict", json=sample_payload("adaptive_sequencing"))
        assert resp.status_code == 200
        assert len(resp.json()["predictions"]) == 3


def test_mlflow_register_recommendation(tmp_path: Path, monkeypatch):
    db = tmp_path / "mlflow.db"
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{db}")
    result = train_recommendation_model(
        artifact_dir=tmp_path / "art", register=True, n_learners=40, seed=2
    )
    assert result["mlflow_run_id"]
    assert result["model_version"]
