"""Inference for career-forecast role suitability predictions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from asiwdp_ml.career_forecast.features import feature_matrix
from asiwdp_ml.common.explainability import career_forecast_rationale
from asiwdp_ml.common.metadata import ModelMetadata


class CareerForecastModel:
    def __init__(self, artifact_dir: str | Path) -> None:
        self.artifact_dir = Path(artifact_dir)
        bundle = joblib.load(self.artifact_dir / "model.joblib")
        self.model = bundle["model"]
        self.label_encoder = bundle["label_encoder"]
        self.metadata = ModelMetadata.model_validate(
            json.loads((self.artifact_dir / "metadata.json").read_text(encoding="utf-8"))
        )

    def predict(self, payload: dict[str, Any], top_k: int = 3) -> dict[str, Any]:
        df = pd.DataFrame([payload])
        X = feature_matrix(df)
        proba = self.model.predict_proba(X)[0]
        classes = self.label_encoder.classes_
        order = proba.argsort()[::-1][:top_k]

        predictions: list[dict[str, Any]] = []
        for idx in order:
            role = str(classes[idx])
            probability = float(proba[idx])
            predictions.append(
                {
                    "role_id": role,
                    "probability": probability,
                    "suitability_score": probability,
                    "rationale": career_forecast_rationale(
                        predicted_role=role,
                        probability=probability,
                        current_role=str(payload.get("current_role", "unknown")),
                        skill_growth_rate=float(payload.get("skill_growth_rate", 0.0)),
                        competency_coverage=float(payload.get("competency_coverage", 0.0)),
                        prior_transition_rate=(
                            float(payload["prior_transition_rate"])
                            if "prior_transition_rate" in payload
                            else None
                        ),
                    ),
                }
            )

        top = predictions[0]
        return {
            "predictions": predictions,
            "rationale": top["rationale"],
            "model_metadata": self.metadata.to_dict(),
        }
