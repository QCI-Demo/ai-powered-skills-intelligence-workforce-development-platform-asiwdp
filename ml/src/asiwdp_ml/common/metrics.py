"""Ranking and classification metrics for ASIWDP models."""

from __future__ import annotations

import numpy as np
import pandas as pd


def average_precision_at_k(y_true: list[int], y_score: list[float], k: int = 5) -> float:
    """Average precision at K for a single ranked list."""
    if k <= 0:
        return 0.0
    order = np.argsort(y_score)[::-1][:k]
    hits = 0
    precision_sum = 0.0
    for rank, idx in enumerate(order, start=1):
        if y_true[idx] > 0:
            hits += 1
            precision_sum += hits / rank
    if hits == 0:
        return 0.0
    # Normalize by min(k, number of relevant) — classic AP@k uses min(k, |rel|).
    n_relevant = min(k, int(sum(1 for y in y_true if y > 0)))
    if n_relevant == 0:
        return 0.0
    return precision_sum / n_relevant


def mean_average_precision_at_k(
    df: pd.DataFrame,
    *,
    group_col: str = "learner_id",
    label_col: str = "label",
    score_col: str = "score",
    k: int = 5,
) -> float:
    """MAP@K across learners (or other groups)."""
    aps: list[float] = []
    for _, group in df.groupby(group_col):
        y_true = group[label_col].astype(int).tolist()
        y_score = group[score_col].astype(float).tolist()
        if sum(y_true) == 0:
            continue
        aps.append(average_precision_at_k(y_true, y_score, k=k))
    if not aps:
        return 0.0
    return float(np.mean(aps))


def top_k_accuracy(y_true: np.ndarray, proba: np.ndarray, k: int = 3) -> float:
    """Fraction of samples where true class is in top-k predicted classes."""
    if proba.ndim != 2:
        raise ValueError("proba must be 2-D")
    k = min(k, proba.shape[1])
    topk = np.argsort(proba, axis=1)[:, -k:]
    hits = [int(y_true[i] in topk[i]) for i in range(len(y_true))]
    return float(np.mean(hits)) if hits else 0.0
