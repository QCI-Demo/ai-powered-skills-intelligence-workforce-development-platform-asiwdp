"""Rationale string builders for explainable model outputs."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def recommendation_rationale(
    *,
    content_id: str,
    rank: int,
    score: float,
    skill_gap_mean: float,
    content_relevance: float,
    top_features: Sequence[tuple[str, float]] | None = None,
) -> str:
    gap_pct = int(round(skill_gap_mean * 100))
    rel_pct = int(round(content_relevance * 100))
    base = (
        f"Ranked #{rank} ({content_id}) with score {score:.3f} because the learner's "
        f"mean skill-gap is {gap_pct}% and content relevance is {rel_pct}%."
    )
    if top_features:
        drivers = ", ".join(f"{name}={value:.3f}" for name, value in top_features[:3])
        return f"{base} Top drivers: {drivers}."
    return base


def career_forecast_rationale(
    *,
    predicted_role: str,
    probability: float,
    current_role: str,
    skill_growth_rate: float,
    competency_coverage: float,
    prior_transition_rate: float | None = None,
) -> str:
    growth_pct = int(round(skill_growth_rate * 100))
    coverage_pct = int(round(competency_coverage * 100))
    parts = [
        f"Predicted next role '{predicted_role}' at {probability:.1%} probability "
        f"from current role '{current_role}'.",
        f"Skill growth rate ≈ {growth_pct}% and competency coverage ≈ {coverage_pct}%.",
    ]
    if prior_transition_rate is not None:
        parts.append(
            f"Organizational role-map prior transition rate ≈ {prior_transition_rate:.1%}."
        )
    return " ".join(parts)


def sequencing_rationale(
    *,
    module_id: str,
    position: int,
    suitability: float,
    module_difficulty: float,
    learner_proficiency: float,
) -> str:
    diff_pct = int(round(module_difficulty * 100))
    prof_pct = int(round(learner_proficiency * 100))
    gap = module_difficulty - learner_proficiency
    zone = "stretch" if gap > 0.05 else "consolidation" if gap < -0.05 else "matched"
    return (
        f"Sequence position #{position} for {module_id} (suitability {suitability:.3f}): "
        f"module difficulty {diff_pct}% vs learner proficiency {prof_pct}% "
        f"({zone} zone)."
    )


def feature_contribution_pairs(
    feature_names: Sequence[str],
    values: Mapping[str, Any] | Sequence[float],
    importances: Mapping[str, float] | None = None,
    top_n: int = 3,
) -> list[tuple[str, float]]:
    """Select top feature drivers by |importance × value| when available."""
    if isinstance(values, Mapping):
        value_map = {k: float(values[k]) for k in feature_names if k in values}
    else:
        value_map = {name: float(val) for name, val in zip(feature_names, values)}

    if importances:
        scored = [
            (name, abs(importances.get(name, 0.0) * value_map.get(name, 0.0)))
            for name in feature_names
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [(name, value_map.get(name, 0.0)) for name, _ in scored[:top_n]]

    # Fallback: largest absolute feature values.
    scored = sorted(value_map.items(), key=lambda x: abs(x[1]), reverse=True)
    return scored[:top_n]
