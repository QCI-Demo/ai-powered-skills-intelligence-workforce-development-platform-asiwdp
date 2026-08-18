"""Skills Framework service client for role-transition and role-map data.

Uses the organizational role graph to enrich career-forecast training.
When SKILLS_FRAMEWORK_URL is unset, returns deterministic synthetic
role-transition statistics (no employee PII).
"""

from __future__ import annotations

import os
from typing import Any

import httpx
import numpy as np
import pandas as pd

from asiwdp_ml.common.feature_store import ROLE_IDS


class SkillsFrameworkClient:
    """Gather role transition data from the Skills Framework service."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout_seconds: float = 15.0,
        seed: int = 7,
    ) -> None:
        self.base_url = (base_url or os.getenv("SKILLS_FRAMEWORK_URL", "")).rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.seed = seed

    def fetch_role_transition_matrix(self, tenant_id: str = "tenant_demo") -> pd.DataFrame:
        """Return historical from_role → to_role transition counts / rates."""
        if self.base_url:
            return self._fetch_remote(tenant_id)
        return self._synthetic_transitions(tenant_id)

    def fetch_role_skill_requirements(self, tenant_id: str = "tenant_demo") -> pd.DataFrame:
        """Return role → required skill coverage expectations."""
        if self.base_url:
            url = f"{self.base_url}/api/v1/roles/skill-requirements"
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(url, params={"tenant_id": tenant_id})
                response.raise_for_status()
                return pd.DataFrame(response.json()["items"])
        rng = np.random.default_rng(self.seed)
        rows: list[dict[str, Any]] = []
        for idx, role in enumerate(ROLE_IDS):
            rows.append(
                {
                    "tenant_id": tenant_id,
                    "role_id": role,
                    "required_skill_count": 5 + idx * 2,
                    "min_competency_coverage": round(0.4 + 0.08 * idx, 3),
                    "seniority_level": idx,
                    "avg_time_in_role_months": float(rng.uniform(8, 30)),
                }
            )
        return pd.DataFrame(rows)

    def _fetch_remote(self, tenant_id: str) -> pd.DataFrame:
        url = f"{self.base_url}/api/v1/roles/transitions"
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.get(url, params={"tenant_id": tenant_id})
            response.raise_for_status()
            payload = response.json()
        return pd.DataFrame(payload.get("items", payload))

    def _synthetic_transitions(self, tenant_id: str) -> pd.DataFrame:
        rng = np.random.default_rng(self.seed)
        rows: list[dict[str, Any]] = []
        for i, from_role in enumerate(ROLE_IDS):
            for j, to_role in enumerate(ROLE_IDS):
                if i == j:
                    continue
                distance = abs(j - i)
                base = max(1, int(40 / (1 + distance)))
                if j < i:
                    base = max(1, base // 3)
                count = int(rng.integers(base, base + 15))
                rows.append(
                    {
                        "tenant_id": tenant_id,
                        "from_role": from_role,
                        "to_role": to_role,
                        "transition_count": count,
                        "avg_months_to_transition": float(6 + distance * 4 + rng.normal(0, 1)),
                        "success_rate": float(np.clip(0.9 - 0.12 * distance + rng.normal(0, 0.03), 0.2, 0.98)),
                    }
                )
        df = pd.DataFrame(rows)
        totals = df.groupby("from_role")["transition_count"].transform("sum")
        df["transition_rate"] = df["transition_count"] / totals
        return df

    def enrich_career_features(self, learner_df: pd.DataFrame) -> pd.DataFrame:
        """Join role-map priors onto learner temporal features."""
        transitions = self.fetch_role_transition_matrix()
        role_reqs = self.fetch_role_skill_requirements()
        # Most common next role prior per current role.
        top = (
            transitions.sort_values("transition_rate", ascending=False)
            .groupby("from_role", as_index=False)
            .first()[["from_role", "to_role", "transition_rate", "avg_months_to_transition"]]
            .rename(
                columns={
                    "from_role": "current_role",
                    "to_role": "prior_top_next_role",
                    "transition_rate": "prior_transition_rate",
                    "avg_months_to_transition": "prior_avg_months",
                }
            )
        )
        reqs = role_reqs.rename(columns={"role_id": "current_role"})[
            ["current_role", "min_competency_coverage", "seniority_level"]
        ]
        out = learner_df.merge(top, on="current_role", how="left")
        out = out.merge(reqs, on="current_role", how="left")
        out["coverage_vs_role_min"] = out["competency_coverage"] - out["min_competency_coverage"]
        out["tenure_vs_prior_months"] = out["tenure_months"] - out["prior_avg_months"]
        return out
