# ASIWDP ML Models

Recommendation ranking, career-forecast, and adaptive-sequencing models for the
AI-Powered Skills Intelligence & Workforce Development Platform.

| Model | Algorithm | Primary metric | Registered name |
|-------|-----------|----------------|-----------------|
| Recommendation ranker | XGBoost classifier | MAP@5 | `asiwdp-recommendation-ranker` |
| Career forecast | Gradient Boosting classifier | accuracy / top-3 | `asiwdp-career-forecast` |
| Adaptive sequencing | XGBoost regressor | RMSE + MAP@5 proxy | `asiwdp-adaptive-sequencing` |

All `/predict` responses include:

- `predictions` — ranked items / roles / modules
- `rationale` — human-readable explanation string
- `model_metadata` — name, version, stage, framework, metrics, `trained_at`

## Layout

```
ml/
  src/asiwdp_ml/
    common/           # feature store, skills framework, metrics, MLflow registry
    recommendation/
    career_forecast/
    adaptive_sequencing/
    serving/          # FastAPI /predict + /health
  projects/*/         # MLproject, conda.yaml, Dockerfile per model
  scripts/promote_model.py
```

## Quick start

```bash
pip install -e "ml[dev]"

# Train (writes artifacts/*, registers to local SQLite MLflow store)
export MLFLOW_TRACKING_URI=sqlite:///mlflow.db
python -m asiwdp_ml.recommendation.train --artifact-dir artifacts/recommendation
python -m asiwdp_ml.career_forecast.train --artifact-dir artifacts/career_forecast
python -m asiwdp_ml.adaptive_sequencing.train --artifact-dir artifacts/adaptive_sequencing

# Serve locally
MODEL_KIND=recommendation MODEL_ARTIFACT_DIR=artifacts/recommendation \
  uvicorn asiwdp_ml.serving.main:app --port 8080

# Promote Staging → Production
python ml/scripts/promote_model.py --model recommendation --version 1
```

## Docker

Build from repository root after training artifacts exist:

```bash
docker build -f ml/projects/recommendation/Dockerfile -t asiwdp-recommendation .
docker run --rm -p 8080:8080 asiwdp-recommendation
curl -s localhost:8080/health | jq .
```

## MLflow projects

```bash
mlflow run ml/projects/recommendation -P n_learners=200
mlflow run ml/projects/career_forecast -P n_learners=300
mlflow run ml/projects/adaptive_sequencing -P n_learners=250
```

## Tests

```bash
pip install -e "ml[dev]"
pytest tests/ml -q
```

Training data is synthetic and anonymized (`learner_NNNN` IDs only) unless
`FEATURE_STORE_URI` / `SKILLS_FRAMEWORK_URL` point at platform services.
