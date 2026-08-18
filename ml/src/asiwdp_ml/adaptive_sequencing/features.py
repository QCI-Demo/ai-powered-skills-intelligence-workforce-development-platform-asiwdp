"""Features for adaptive module sequencing by difficulty and proficiency."""

from __future__ import annotations

import pandas as pd

FEATURE_COLUMNS = [
    "module_difficulty",
    "learner_proficiency",
    "prerequisite_mastery",
    "difficulty_gap",
    "abs_difficulty_gap",
    "recent_success_rate",
    "module_estimated_minutes",
    "optimal_stretch",
    "mastery_x_proficiency",
    "time_burden",
]


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    # Prefer slight stretch above current proficiency (~0.15).
    out["optimal_stretch"] = 1.0 - (out["difficulty_gap"] - 0.15).abs()
    out["mastery_x_proficiency"] = out["prerequisite_mastery"] * out["learner_proficiency"]
    out["time_burden"] = out["module_estimated_minutes"] / 60.0
    return out


def feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    engineered = engineer_features(df)
    missing = [c for c in FEATURE_COLUMNS if c not in engineered.columns]
    if missing:
        raise ValueError(f"Missing sequencing features: {missing}")
    return engineered[FEATURE_COLUMNS].astype(float)
