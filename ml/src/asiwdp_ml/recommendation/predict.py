"""Inference helpers for the recommendation ranking model."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from asiwdp_ml.common.explainability import feature_contribution_pairs, recommendation_rationale
from asiwdp_ml.common.metadata import ModelMetadata
from asiwdp_ml.recommendation.features import ALL_FEATURE_COLUMNS, feature_matrix


class RecommendationModel:
    def __init__(self, artifact_dir: str | Path) -> None:
        self.artifact_dir = Path(artifact_dir)
        self.model = joblib.load(self.artifact_dir / "model.joblib")
        self.metadata = ModelMetadata.model_validate(
            json.loads((self.artifact_dir / "metadata.json").read_text(encoding="utf-8"))
        )
        self.feature_names = json.loads(
            (self.artifact_dir / "feature_names.json").read_text(encoding="utf-8")
        )
        extras_path = self.artifact_dir / "extras.json"
        self.importances = {}
        if extras_path.exists():
            extras = json.loads(extras_path.read_text(encoding="utf-8"))
            self.importances = extras.get("feature_importances", {})

    def predict(self, candidates: list[dict[str, Any]], top_k: int = 5) -> dict[str, Any]:
        df = pd.DataFrame(candidates)
        X = feature_matrix(df)
        scores = self.model.predict_proba(X)[:, 1]
        ranked = df.copy()
        ranked["score"] = scores
        ranked = ranked.sort_values("score", ascending=False).head(top_k)

        items: list[dict[str, Any]] = []
        for rank, (_, row) in enumerate(ranked.iterrows(), start=1):
            feat_vals = {c: float(row[c]) if c in row else float(X.loc[row.name, c]) for c in ALL_FEATURE_COLUMNS}
            # Ensure engineered cols present via X
            for c in ALL_FEATURE_COLUMNS:
                feat_vals[c] = float(X.loc[row.name, c])
            drivers = feature_contribution_pairs(ALL_FEATURE_COLUMNS, feat_vals, self.importances)
            items.append(
                {
                    "content_id": str(row["content_id"]),
                    "rank": rank,
                    "score": float(row["score"]),
                    "rationale": recommendation_rationale(
                        content_id=str(row["content_id"]),
                        rank=rank,
                        score=float(row["score"]),
                        skill_gap_mean=float(row.get("skill_gap_mean", feat_vals["skill_gap_mean"])),
                        content_relevance=float(
                            row.get("content_relevance", feat_vals["content_relevance"])
                        ),
                        top_features=drivers,
                    ),
                }
            )
        return {
            "predictions": items,
            "rationale": (
                f"Returned top-{len(items)} learning items ranked by predicted engagement "
                f"from skill-gap, relevance, and activity features."
            ),
            "model_metadata": self.metadata.to_dict(),
        }
