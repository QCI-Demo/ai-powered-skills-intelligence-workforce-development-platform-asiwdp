"""Model metadata schema returned with every prediction for explainability."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

MODEL_NAMES = {
    "recommendation": "asiwdp-recommendation-ranker",
    "career_forecast": "asiwdp-career-forecast",
    "adaptive_sequencing": "asiwdp-adaptive-sequencing",
}


class ModelMetadata(BaseModel):
    """Versioned model identity attached to every /predict response."""

    model_name: str
    model_version: str
    mlflow_run_id: str | None = None
    stage: str = "Staging"
    trained_at: str
    framework: str
    metrics: dict[str, float] = Field(default_factory=dict)
    feature_schema_version: str = "1.0.0"

    @classmethod
    def build(
        cls,
        *,
        model_name: str,
        model_version: str,
        framework: str,
        metrics: dict[str, float] | None = None,
        mlflow_run_id: str | None = None,
        stage: str = "Staging",
        feature_schema_version: str = "1.0.0",
        trained_at: str | None = None,
    ) -> ModelMetadata:
        return cls(
            model_name=model_name,
            model_version=model_version,
            mlflow_run_id=mlflow_run_id,
            stage=stage,
            trained_at=trained_at or datetime.now(timezone.utc).isoformat(),
            framework=framework,
            metrics=metrics or {},
            feature_schema_version=feature_schema_version,
        )

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()
