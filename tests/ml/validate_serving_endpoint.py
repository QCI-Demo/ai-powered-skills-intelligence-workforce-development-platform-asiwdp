"""Validate that a live /predict endpoint returns rationale and model metadata."""

from __future__ import annotations

import argparse
import json
import sys

import httpx


def sample_payload(model_kind: str) -> dict:
    if model_kind == "recommendation":
        return {
            "top_k": 3,
            "candidates": [
                {
                    "content_id": "content_001",
                    "skill_gap_mean": 0.7,
                    "skill_gap_max": 0.9,
                    "skill_gap_std": 0.1,
                    "content_relevance": 0.8,
                    "content_difficulty": 0.5,
                    "learner_activity_rate": 0.4,
                    "learner_completion_rate": 0.6,
                    "recent_engagement": 0.3,
                    "content_popularity": 0.5,
                    "hours_since_last_touch": 48,
                },
                {
                    "content_id": "content_002",
                    "skill_gap_mean": 0.2,
                    "skill_gap_max": 0.3,
                    "skill_gap_std": 0.05,
                    "content_relevance": 0.4,
                    "content_difficulty": 0.7,
                    "learner_activity_rate": 0.4,
                    "learner_completion_rate": 0.6,
                    "recent_engagement": 0.2,
                    "content_popularity": 0.8,
                    "hours_since_last_touch": 120,
                },
                {
                    "content_id": "content_003",
                    "skill_gap_mean": 0.55,
                    "skill_gap_max": 0.7,
                    "skill_gap_std": 0.12,
                    "content_relevance": 0.75,
                    "content_difficulty": 0.55,
                    "learner_activity_rate": 0.5,
                    "learner_completion_rate": 0.7,
                    "recent_engagement": 0.4,
                    "content_popularity": 0.6,
                    "hours_since_last_touch": 24,
                },
            ],
        }
    if model_kind == "career_forecast":
        return {
            "top_k": 3,
            "features": {
                "current_role": "role_data_analyst",
                "current_role_idx": 1,
                "tenure_months": 18,
                "skill_growth_rate": 0.1,
                "skill_growth_rate_30d": 0.12,
                "skill_growth_rate_90d": 0.09,
                "competency_coverage": 0.72,
                "learning_velocity": 3.5,
                "modules_completed_90d": 8,
                "avg_assessment_score": 0.81,
                "role_affinity_score": 0.7,
                "org_mobility_index": 0.4,
                "prior_transition_rate": 0.35,
                "prior_avg_months": 14,
                "min_competency_coverage": 0.5,
                "seniority_level": 1,
                "coverage_vs_role_min": 0.22,
                "tenure_vs_prior_months": 4,
            },
        }
    if model_kind == "adaptive_sequencing":
        return {
            "modules": [
                {
                    "module_id": "module_001",
                    "module_difficulty": 0.3,
                    "learner_proficiency": 0.45,
                    "prerequisite_mastery": 0.5,
                    "difficulty_gap": -0.15,
                    "abs_difficulty_gap": 0.15,
                    "recent_success_rate": 0.6,
                    "module_estimated_minutes": 25,
                },
                {
                    "module_id": "module_010",
                    "module_difficulty": 0.55,
                    "learner_proficiency": 0.45,
                    "prerequisite_mastery": 0.5,
                    "difficulty_gap": 0.1,
                    "abs_difficulty_gap": 0.1,
                    "recent_success_rate": 0.6,
                    "module_estimated_minutes": 40,
                },
                {
                    "module_id": "module_020",
                    "module_difficulty": 0.85,
                    "learner_proficiency": 0.45,
                    "prerequisite_mastery": 0.4,
                    "difficulty_gap": 0.4,
                    "abs_difficulty_gap": 0.4,
                    "recent_success_rate": 0.55,
                    "module_estimated_minutes": 70,
                },
            ]
        }
    raise ValueError(f"unknown model_kind={model_kind}")


def validate(base_url: str, model_kind: str) -> None:
    health = httpx.get(f"{base_url.rstrip('/')}/health", timeout=30.0)
    health.raise_for_status()
    health_body = health.json()
    assert health_body.get("status") == "ok", health_body
    assert health_body.get("model_metadata"), "health missing model_metadata"

    response = httpx.post(
        f"{base_url.rstrip('/')}/predict",
        json=sample_payload(model_kind),
        timeout=60.0,
    )
    response.raise_for_status()
    body = response.json()
    assert "rationale" in body and isinstance(body["rationale"], str) and body["rationale"], body
    assert "model_metadata" in body and body["model_metadata"].get("model_version"), body
    assert "predictions" in body and len(body["predictions"]) >= 1, body
    # Per-item rationales when present
    for item in body["predictions"]:
        assert "rationale" in item and item["rationale"], item
    print(json.dumps({"ok": True, "model_kind": model_kind, "n_predictions": len(body["predictions"])}))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument(
        "--model-kind",
        required=True,
        choices=["recommendation", "career_forecast", "adaptive_sequencing"],
    )
    args = parser.parse_args(argv)
    validate(args.base_url, args.model_kind)
    return 0


if __name__ == "__main__":
    sys.exit(main())
