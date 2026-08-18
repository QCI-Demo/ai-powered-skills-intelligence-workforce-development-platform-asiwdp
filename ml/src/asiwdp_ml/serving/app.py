"""FastAPI serving factory exposing versioned /predict with rationale + metadata."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from asiwdp_ml.adaptive_sequencing.predict import AdaptiveSequencingModel
from asiwdp_ml.career_forecast.predict import CareerForecastModel
from asiwdp_ml.recommendation.predict import RecommendationModel

ModelKind = Literal["recommendation", "career_forecast", "adaptive_sequencing"]


class PredictRequest(BaseModel):
    """Unified predict payload; fields used depend on MODEL_KIND."""

    learner_id: str | None = None
    tenant_id: str | None = "tenant_demo"
    top_k: int = Field(default=5, ge=1, le=50)
    candidates: list[dict[str, Any]] | None = None
    modules: list[dict[str, Any]] | None = None
    features: dict[str, Any] | None = None


class PredictResponse(BaseModel):
    predictions: list[dict[str, Any]]
    rationale: str
    model_metadata: dict[str, Any]


def create_app(model_kind: ModelKind | None = None, artifact_dir: str | Path | None = None) -> FastAPI:
    kind = (model_kind or os.getenv("MODEL_KIND", "recommendation")).strip()
    artifacts = Path(
        artifact_dir or os.getenv("MODEL_ARTIFACT_DIR", f"/models/{kind}")
    )
    state: dict[str, Any] = {"model": None, "kind": kind, "artifact_dir": str(artifacts)}

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if not artifacts.exists():
            raise RuntimeError(f"Artifact directory not found: {artifacts}")
        if kind == "recommendation":
            state["model"] = RecommendationModel(artifacts)
        elif kind == "career_forecast":
            state["model"] = CareerForecastModel(artifacts)
        elif kind == "adaptive_sequencing":
            state["model"] = AdaptiveSequencingModel(artifacts)
        else:
            raise RuntimeError(f"Unknown MODEL_KIND: {kind}")
        yield

    app = FastAPI(
        title=f"ASIWDP {kind} model server",
        version="1.0.0",
        description="Versioned model serving with explainable rationale and metadata.",
        lifespan=lifespan,
    )

    def _run_predict(body: PredictRequest) -> dict[str, Any]:
        model = state["model"]
        if model is None:
            raise HTTPException(status_code=503, detail="Model not loaded")
        try:
            if kind == "recommendation":
                if not body.candidates:
                    raise HTTPException(status_code=400, detail="candidates required")
                return model.predict(body.candidates, top_k=body.top_k)
            if kind == "career_forecast":
                if not body.features:
                    raise HTTPException(status_code=400, detail="features required")
                return model.predict(body.features, top_k=min(body.top_k, 5))
            if kind == "adaptive_sequencing":
                if not body.modules:
                    raise HTTPException(status_code=400, detail="modules required")
                return model.predict(body.modules)
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        raise HTTPException(status_code=500, detail="Unhandled model kind")

    @app.get("/health")
    @app.get("/api/v1/health")
    def health() -> dict[str, Any]:
        meta = None
        if state["model"] is not None:
            meta = state["model"].metadata.to_dict()
        return {"status": "ok", "model_kind": kind, "model_metadata": meta}

    @app.post("/predict", response_model=PredictResponse)
    @app.post("/api/v1/predict", response_model=PredictResponse)
    def predict(body: PredictRequest) -> dict[str, Any]:
        return _run_predict(body)

    return app
