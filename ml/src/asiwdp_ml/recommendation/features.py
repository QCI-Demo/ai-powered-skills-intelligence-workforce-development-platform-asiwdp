"""Feature engineering for recommendation ranking."""

from __future__ import annotations

import pandas as pd

FEATURE_COLUMNS = [
    "skill_gap_mean",
    "skill_gap_max",
    "skill_gap_std",
    "content_relevance",
    "content_difficulty",
    "learner_activity_rate",
    "learner_completion_rate",
    "recent_engagement",
    "content_popularity",
    "hours_since_last_touch",
]

# Engineered interaction features appended in engineer_features().
ENGINEERED_COLUMNS = [
    "gap_x_relevance",
    "gap_minus_difficulty",
    "activity_x_engagement",
    "completion_x_popularity",
    "recency_decay",
]

ALL_FEATURE_COLUMNS = FEATURE_COLUMNS + ENGINEERED_COLUMNS


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Combine gap scores, content relevance, and learner activity signals."""
    out = df.copy()
    out["gap_x_relevance"] = out["skill_gap_mean"] * out["content_relevance"]
    out["gap_minus_difficulty"] = out["skill_gap_mean"] - out["content_difficulty"]
    out["activity_x_engagement"] = out["learner_activity_rate"] * out["recent_engagement"]
    out["completion_x_popularity"] = out["learner_completion_rate"] * out["content_popularity"]
    # Soft recency decay: fresher activity → higher signal.
    out["recency_decay"] = 1.0 / (1.0 + out["hours_since_last_touch"] / 168.0)
    return out


def feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    engineered = engineer_features(df)
    missing = [c for c in ALL_FEATURE_COLUMNS if c not in engineered.columns]
    if missing:
        raise ValueError(f"Missing recommendation features: {missing}")
    return engineered[ALL_FEATURE_COLUMNS]
