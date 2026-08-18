"""Inference for adaptive module sequencing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from asiwdp_ml.adaptive_sequencing.features import feature_matrix
from asiwdp_ml.common.explainability import sequencing_rationale
from asiwdp_ml.common.metadata import ModelMetadata


class AdaptiveSequencingModel:
    def __init__(self, artifact_dir: str | Path) -> None:
        self.artifact_dir = Path(artifact_dir)
        self.model = joblib.load(self.artifact_dir / "model.joblib")
        self.metadata = ModelMetadata.model_validate(
            json.loads((self.artifact_dir / "metadata.json").read_text(encoding="utf-8"))
        )

    def predict(self, modules: list[dict[str, Any]]) -> dict[str, Any]:
        df = pd.DataFrame(modules)
        X = feature_matrix(df)
        scores = self.model.predict(X)
        ranked = df.copy()
        ranked["suitability"] = scores
        ranked = ranked.sort_values("suitability", ascending=False)

        sequence: list[dict[str, Any]] = []
        for position, (_, row) in enumerate(ranked.iterrows(), start=1):
            sequence.append(
                {
                    "module_id": str(row["module_id"]),
                    "position": position,
                    "suitability": float(row["suitability"]),
                    "module_difficulty": float(row["module_difficulty"]),
                    "learner_proficiency": float(row["learner_proficiency"]),
                    "rationale": sequencing_rationale(
                        module_id=str(row["module_id"]),
                        position=position,
                        suitability=float(row["suitability"]),
                        module_difficulty=float(row["module_difficulty"]),
                        learner_proficiency=float(row["learner_proficiency"]),
                    ),
                }
            )

        return {
            "predictions": sequence,
            "rationale": (
                f"Ordered {len(sequence)} modules by predicted suitability given "
                f"difficulty relative to learner proficiency."
            ),
            "model_metadata": self.metadata.to_dict(),
        }
