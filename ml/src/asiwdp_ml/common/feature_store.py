"""Feature-store client for historic learner activity and competency features.

Extracts anonymized training frames used by recommendation, career-forecast,
and adaptive-sequencing models. Real deployments point FEATURE_STORE_URI at
the platform feature store; local/CI uses deterministic synthetic data with
no personal identifiers.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# Synthetic skill / content vocabularies (platform IDs only — no PII).
SKILL_IDS = [f"skill_{i:03d}" for i in range(1, 21)]
CONTENT_IDS = [f"content_{i:03d}" for i in range(1, 51)]
ROLE_IDS = [
    "role_junior_analyst",
    "role_data_analyst",
    "role_senior_analyst",
    "role_data_engineer",
    "role_ml_engineer",
    "role_team_lead",
]
MODULE_IDS = [f"module_{i:03d}" for i in range(1, 31)]


class FeatureStoreClient:
    """Read-only client for skill-gap, activity, and content feature tables."""

    def __init__(
        self,
        uri: str | None = None,
        seed: int = 42,
        cache_dir: str | Path | None = None,
    ) -> None:
        self.uri = uri or os.getenv("FEATURE_STORE_URI", "synthetic://local")
        self.seed = seed
        self.cache_dir = Path(cache_dir or os.getenv("ASIWDP_ML_CACHE", "/tmp/asiwdp-ml-cache"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _rng(self) -> np.random.Generator:
        return np.random.default_rng(self.seed)

    def extract_recommendation_training_data(self, n_learners: int = 200) -> pd.DataFrame:
        """Extract learner×content rows with gap scores, relevance, and activity.

        Columns are engineered for gradient-boosted ranking (XGBoost).
        """
        if self.uri.startswith("file://"):
            path = Path(self.uri.removeprefix("file://"))
            return pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)

        rng = self._rng()
        rows: list[dict[str, Any]] = []
        for learner_idx in range(n_learners):
            learner_id = f"learner_{learner_idx:04d}"
            # Per-learner skill-gap vector (0 = proficient, 1 = large gap).
            gap_vector = rng.uniform(0.0, 1.0, size=len(SKILL_IDS))
            activity_rate = float(rng.uniform(0.05, 0.9))
            completion_rate = float(rng.uniform(0.1, 0.95))
            for content_idx, content_id in enumerate(CONTENT_IDS):
                # Content aligns to a small skill subset.
                primary_skill = content_idx % len(SKILL_IDS)
                related = [(primary_skill + k) % len(SKILL_IDS) for k in range(3)]
                gap_score = float(np.mean(gap_vector[related]))
                content_difficulty = 0.2 + 0.6 * ((content_idx % 5) / 4.0)
                content_relevance = float(
                    1.0 - abs(gap_score - content_difficulty) + rng.normal(0, 0.05)
                )
                content_relevance = float(np.clip(content_relevance, 0.0, 1.0))
                engagement = float(rng.beta(2, 5) * activity_rate)
                # Label: clicked / completed (relevance + gap driven).
                click_prob = 0.15 + 0.55 * gap_score * content_relevance + 0.2 * engagement
                label = int(rng.random() < np.clip(click_prob, 0.05, 0.95))
                rows.append(
                    {
                        "tenant_id": "tenant_demo",
                        "learner_id": learner_id,
                        "content_id": content_id,
                        "skill_gap_mean": gap_score,
                        "skill_gap_max": float(np.max(gap_vector[related])),
                        "skill_gap_std": float(np.std(gap_vector[related])),
                        "content_relevance": content_relevance,
                        "content_difficulty": content_difficulty,
                        "learner_activity_rate": activity_rate,
                        "learner_completion_rate": completion_rate,
                        "recent_engagement": engagement,
                        "content_popularity": float(0.3 + 0.7 * ((content_idx % 7) / 6.0)),
                        "hours_since_last_touch": float(rng.uniform(1, 720)),
                        "label": label,
                    }
                )
        return pd.DataFrame(rows)

    def extract_career_forecast_training_data(self, n_learners: int = 300) -> pd.DataFrame:
        """Extract temporal skill-progression features and target next roles."""
        if self.uri.startswith("file://"):
            path = Path(self.uri.removeprefix("file://"))
            return pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)

        rng = self._rng()
        rows: list[dict[str, Any]] = []
        for i in range(n_learners):
            current_role_idx = int(rng.integers(0, len(ROLE_IDS) - 1))
            current_role = ROLE_IDS[current_role_idx]

            tenure_months = float(rng.uniform(3, 48))
            skill_growth_rate = float(rng.normal(0.08, 0.04))
            skill_growth_rate = float(np.clip(skill_growth_rate, -0.05, 0.25))
            competency_coverage = float(rng.uniform(0.2, 0.95))
            learning_velocity = float(rng.uniform(0.5, 8.0))
            role_affinity = float(rng.uniform(0.1, 1.0))
            org_mobility = float(rng.uniform(0.0, 1.0))
            modules_completed = float(rng.integers(0, 25))
            avg_assessment = float(rng.uniform(0.4, 0.98))

            # Next-role labels are mostly deterministic from readiness so the
            # classifier can learn: high coverage/growth/velocity → adjacent
            # senior role; low readiness → lateral/same band.
            readiness = (
                0.35 * competency_coverage
                + 0.25 * np.clip(skill_growth_rate / 0.2, 0, 1)
                + 0.20 * np.clip(learning_velocity / 8.0, 0, 1)
                + 0.10 * np.clip(tenure_months / 36.0, 0, 1)
                + 0.10 * org_mobility
            )
            if readiness >= 0.72 and current_role_idx < len(ROLE_IDS) - 1:
                target_idx = min(current_role_idx + 2, len(ROLE_IDS) - 1)
            elif readiness >= 0.55 and current_role_idx < len(ROLE_IDS) - 1:
                target_idx = current_role_idx + 1
            elif readiness <= 0.35 and current_role_idx > 0:
                target_idx = current_role_idx - 1
            else:
                target_idx = current_role_idx
            # Light label noise (~12%) keeps the task realistic without
            # destroying learnable structure.
            if rng.random() < 0.12:
                target_idx = int(rng.integers(0, len(ROLE_IDS)))
            next_role = ROLE_IDS[target_idx]

            rows.append(
                {
                    "tenant_id": "tenant_demo",
                    "learner_id": f"learner_{i:04d}",
                    "current_role": current_role,
                    "current_role_idx": current_role_idx,
                    "tenure_months": tenure_months,
                    "skill_growth_rate": skill_growth_rate,
                    "skill_growth_rate_30d": skill_growth_rate * float(rng.uniform(0.6, 1.4)),
                    "skill_growth_rate_90d": skill_growth_rate * float(rng.uniform(0.7, 1.2)),
                    "competency_coverage": competency_coverage,
                    "learning_velocity": learning_velocity,
                    "modules_completed_90d": modules_completed,
                    "avg_assessment_score": avg_assessment,
                    "role_affinity_score": role_affinity,
                    "org_mobility_index": org_mobility,
                    "next_role": next_role,
                }
            )
        return pd.DataFrame(rows)

    def extract_sequencing_training_data(self, n_learners: int = 250) -> pd.DataFrame:
        """Extract module difficulty × learner proficiency pairs for sequencing."""
        if self.uri.startswith("file://"):
            path = Path(self.uri.removeprefix("file://"))
            return pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)

        rng = self._rng()
        rows: list[dict[str, Any]] = []
        for i in range(n_learners):
            proficiency = float(rng.uniform(0.1, 0.95))
            for mod_idx, module_id in enumerate(MODULE_IDS):
                difficulty = 0.15 + 0.8 * (mod_idx / max(len(MODULE_IDS) - 1, 1))
                prerequisite_mastery = float(np.clip(proficiency + rng.normal(0, 0.1), 0, 1))
                # Optimal order score: prefer modules slightly above proficiency.
                delta = difficulty - proficiency
                success_prob = float(np.clip(1.0 - abs(delta - 0.15) * 1.8, 0.05, 0.95))
                completed = int(rng.random() < success_prob)
                time_on_task = float(rng.uniform(10, 120) * (1 + abs(delta)))
                rows.append(
                    {
                        "tenant_id": "tenant_demo",
                        "learner_id": f"learner_{i:04d}",
                        "module_id": module_id,
                        "module_difficulty": difficulty,
                        "learner_proficiency": proficiency,
                        "prerequisite_mastery": prerequisite_mastery,
                        "difficulty_gap": delta,
                        "abs_difficulty_gap": abs(delta),
                        "recent_success_rate": float(np.clip(proficiency + rng.normal(0, 0.08), 0, 1)),
                        "module_estimated_minutes": float(20 + mod_idx * 3),
                        "time_on_task_minutes": time_on_task,
                        "label_success": completed,
                        # Ranking target: higher = better next module.
                        "suitability": success_prob,
                    }
                )
        return pd.DataFrame(rows)

    def write_cache(self, name: str, df: pd.DataFrame) -> Path:
        path = self.cache_dir / f"{name}.parquet"
        try:
            df.to_parquet(path, index=False)
        except Exception:
            path = self.cache_dir / f"{name}.csv"
            df.to_csv(path, index=False)
        return path
