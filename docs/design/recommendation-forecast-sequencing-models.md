# Recommendation, Career Forecast & Adaptive Sequencing Models

Story: `aa7842d6-de6d-4fa4-822f-b86245c6be73`  
Epic: AI-Powered Recommendation Engine & Adaptive Learning Path Service  
Project: ASIWDP

## Scope

Three model-serving components trained on historic learner activity and
competency features, packaged with MLflow, and exposed via versioned REST
`/predict` endpoints. Every response carries rationale strings and model
metadata for explainability.

## Components

### 1. Recommendation ranking (`8b332081-…`)

1. Extract training rows from the feature store (`FeatureStoreClient`).
2. Engineer gap × relevance × activity features.
3. Train XGBoost binary classifier; evaluate **MAP@5**.
4. Persist artifact + register `asiwdp-recommendation-ranker` in MLflow.

### 2. Career forecast (`1dc1b5b9-…`)

1. Gather role-transition priors from Skills Framework client.
2. Build temporal features (growth rates, coverage vs role minimums).
3. Train `GradientBoostingClassifier` (tree-based alternative to RNN).
4. Register `asiwdp-career-forecast` in MLflow.

### 3. Adaptive sequencing (story component)

Orders modules by difficulty relative to learner proficiency using an XGBoost
suitability regressor (`asiwdp-adaptive-sequencing`).

### 4. MLflow packaging & versioned serving (`981f17a4-…`)

- `MLproject` + `conda.yaml` per model under `ml/projects/`
- Dockerfiles exposing `/predict` and `/health`
- GitHub Actions workflow: train → test → register → image build → endpoint
  validation → optional Staging→Production promotion

## Explainability contract

```json
{
  "predictions": [{ "...": "...", "rationale": "..." }],
  "rationale": "summary explanation",
  "model_metadata": {
    "model_name": "asiwdp-recommendation-ranker",
    "model_version": "1",
    "stage": "Staging",
    "framework": "xgboost",
    "trained_at": "2026-08-18T00:00:00+00:00",
    "metrics": {"map_at_5": 0.42},
    "feature_schema_version": "1.0.0"
  }
}
```

## Privacy

Synthetic training paths use opaque learner IDs only. No employee PII is
embedded in artifacts, logs, or sample payloads. Production feature-store
extracts must remain tenant-scoped and follow platform data-privacy policy.
