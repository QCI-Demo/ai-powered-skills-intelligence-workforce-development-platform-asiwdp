"""Temporal feature engineering for career-forecast classification."""

from __future__ import annotations

import pandas as pd

from asiwdp_ml.common.feature_store import ROLE_IDS

NUMERIC_FEATURES = [
    "tenure_months",
    "skill_growth_rate",
    "skill_growth_rate_30d",
    "skill_growth_rate_90d",
    "competency_coverage",
    "learning_velocity",
    "modules_completed_90d",
    "avg_assessment_score",
    "role_affinity_score",
    "org_mobility_index",
    "current_role_idx",
    "prior_transition_rate",
    "prior_avg_months",
    "min_competency_coverage",
    "seniority_level",
    "coverage_vs_role_min",
    "tenure_vs_prior_months",
    "growth_acceleration",
    "velocity_x_coverage",
]

TARGET_COL = "next_role"
ROLE_LABELS = list(ROLE_IDS)


def engineer_temporal_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create temporal / interaction features from skill progression signals."""
    out = df.copy()
    out["growth_acceleration"] = out["skill_growth_rate_30d"] - out["skill_growth_rate_90d"]
    out["velocity_x_coverage"] = out["learning_velocity"] * out["competency_coverage"]
    # Fill role-map priors if enrichment skipped.
    for col, default in [
        ("prior_transition_rate", 0.0),
        ("prior_avg_months", out["tenure_months"].median() if len(out) else 12.0),
        ("min_competency_coverage", 0.5),
        ("seniority_level", out.get("current_role_idx", 0)),
    ]:
        if col not in out.columns:
            out[col] = default
        out[col] = out[col].fillna(default if not isinstance(default, pd.Series) else default)
    if "coverage_vs_role_min" not in out.columns:
        out["coverage_vs_role_min"] = out["competency_coverage"] - out["min_competency_coverage"]
    if "tenure_vs_prior_months" not in out.columns:
        out["tenure_vs_prior_months"] = out["tenure_months"] - out["prior_avg_months"]
    return out


def feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    engineered = engineer_temporal_features(df)
    missing = [c for c in NUMERIC_FEATURES if c not in engineered.columns]
    if missing:
        raise ValueError(f"Missing career-forecast features: {missing}")
    return engineered[NUMERIC_FEATURES].astype(float)
