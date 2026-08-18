"""Train tree-based career-forecast classifier; register with MLflow."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from asiwdp_ml.career_forecast.features import NUMERIC_FEATURES, TARGET_COL, feature_matrix
from asiwdp_ml.common.feature_store import FeatureStoreClient
from asiwdp_ml.common.metadata import MODEL_NAMES, ModelMetadata
from asiwdp_ml.common.metrics import top_k_accuracy
from asiwdp_ml.common.registry import (
    configure_mlflow,
    log_and_register_model,
    write_local_artifact_bundle,
)
from asiwdp_ml.common.skills_framework import SkillsFrameworkClient

DEFAULT_ARTIFACT_DIR = Path(os.getenv("ASIWDP_MODEL_DIR", "artifacts/career_forecast"))


def train_career_forecast_model(
    *,
    artifact_dir: Path | str = DEFAULT_ARTIFACT_DIR,
    register: bool = True,
    n_learners: int = 300,
    seed: int = 42,
) -> dict[str, Any]:
    store = FeatureStoreClient(seed=seed)
    skills = SkillsFrameworkClient(seed=seed)
    raw = store.extract_career_forecast_training_data(n_learners=n_learners)
    enriched = skills.enrich_career_features(raw)
    store.write_cache("career_forecast_training", enriched)

    X = feature_matrix(enriched)
    label_encoder = LabelEncoder()
    y = label_encoder.fit_transform(enriched[TARGET_COL].astype(str))

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=seed, stratify=y
    )

    model = GradientBoostingClassifier(
        n_estimators=100,
        max_depth=3,
        learning_rate=0.08,
        random_state=seed,
    )
    model.fit(X_train, y_train)

    proba = model.predict_proba(X_test)
    preds = model.predict(X_test)
    accuracy = float(accuracy_score(y_test, preds))
    f1 = float(f1_score(y_test, preds, average="weighted"))
    top3 = top_k_accuracy(y_test, proba, k=3)

    importances = {
        name: float(val) for name, val in zip(NUMERIC_FEATURES, model.feature_importances_)
    }

    metadata = ModelMetadata.build(
        model_name=MODEL_NAMES["career_forecast"],
        model_version="0.1.0",
        framework="sklearn.GradientBoostingClassifier",
        metrics={"accuracy": accuracy, "f1_weighted": f1, "top3_accuracy": top3},
        stage="Staging",
    )

    artifact_path = Path(artifact_dir)
    write_local_artifact_bundle(
        artifact_path,
        model_obj={"model": model, "label_encoder": label_encoder},
        metadata=metadata,
        feature_names=NUMERIC_FEATURES,
        extras={
            "feature_importances": importances,
            "classes": label_encoder.classes_.tolist(),
        },
    )

    run_id = None
    model_version = metadata.model_version
    if register:
        configure_mlflow(experiment_name="asiwdp-career-forecast")
        try:
            # Log the estimator for MLflow sklearn flavor.
            run_id, model_version = log_and_register_model(
                model_name=MODEL_NAMES["career_forecast"],
                artifact_path="model",
                registered_model_name=MODEL_NAMES["career_forecast"],
                metrics={"accuracy": accuracy, "f1_weighted": f1, "top3_accuracy": top3},
                params={
                    "n_estimators": 100,
                    "max_depth": 3,
                    "learning_rate": 0.08,
                    "n_learners": n_learners,
                },
                metadata=metadata,
                tags={"model_family": "career_forecast"},
                flavor="sklearn",
                model_obj=model,
            )
            metadata = metadata.model_copy(
                update={"mlflow_run_id": run_id, "model_version": model_version}
            )
            (artifact_path / "metadata.json").write_text(
                json.dumps(metadata.to_dict(), indent=2), encoding="utf-8"
            )
        except Exception as exc:  # noqa: BLE001
            (artifact_path / "mlflow_register_warning.txt").write_text(str(exc), encoding="utf-8")

    return {
        "accuracy": accuracy,
        "f1_weighted": f1,
        "top3_accuracy": top3,
        "artifact_dir": str(artifact_path),
        "mlflow_run_id": run_id,
        "model_version": model_version,
        "metadata": metadata.to_dict(),
        "n_classes": int(len(label_encoder.classes_)),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Train ASIWDP career-forecast model")
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))
    parser.add_argument("--n-learners", type=int, default=300)
    parser.add_argument("--no-register", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    result = train_career_forecast_model(
        artifact_dir=args.artifact_dir,
        register=not args.no_register,
        n_learners=args.n_learners,
        seed=args.seed,
    )
    print(json.dumps({k: v for k, v in result.items() if k != "metadata"}, indent=2))


if __name__ == "__main__":
    main()
