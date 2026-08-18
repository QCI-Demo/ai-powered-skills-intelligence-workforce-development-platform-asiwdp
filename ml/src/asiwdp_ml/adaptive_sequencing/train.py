"""Train adaptive sequencing ranker (XGBoost) ordering modules by suitability."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import xgboost as xgb
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import GroupShuffleSplit

from asiwdp_ml.adaptive_sequencing.features import FEATURE_COLUMNS, feature_matrix
from asiwdp_ml.common.feature_store import FeatureStoreClient
from asiwdp_ml.common.metadata import MODEL_NAMES, ModelMetadata
from asiwdp_ml.common.metrics import mean_average_precision_at_k
from asiwdp_ml.common.registry import (
    configure_mlflow,
    log_and_register_model,
    write_local_artifact_bundle,
)

DEFAULT_ARTIFACT_DIR = Path(os.getenv("ASIWDP_MODEL_DIR", "artifacts/adaptive_sequencing"))


def train_adaptive_sequencing_model(
    *,
    artifact_dir: Path | str = DEFAULT_ARTIFACT_DIR,
    register: bool = True,
    n_learners: int = 250,
    seed: int = 42,
) -> dict[str, Any]:
    store = FeatureStoreClient(seed=seed)
    raw = store.extract_sequencing_training_data(n_learners=n_learners)
    store.write_cache("adaptive_sequencing_training", raw)

    X = feature_matrix(raw)
    y = raw["suitability"].astype(float).values
    groups = raw["learner_id"].values

    splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
    train_idx, test_idx = next(splitter.split(X, y, groups))
    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]

    model = xgb.XGBRegressor(
        n_estimators=80,
        max_depth=4,
        learning_rate=0.08,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="reg:squarederror",
        random_state=seed,
        n_jobs=2,
    )
    model.fit(X_train, y_train)
    pred = model.predict(X_test)
    rmse = float(np.sqrt(mean_squared_error(y_test, pred)))
    r2 = float(r2_score(y_test, pred))

    # Treat top suitability modules as relevant for MAP@5 proxy.
    eval_df = raw.iloc[test_idx][["learner_id"]].copy()
    eval_df["score"] = pred
    eval_df["label"] = (raw.iloc[test_idx]["suitability"].values >= 0.7).astype(int)
    map5 = mean_average_precision_at_k(eval_df, k=5)

    importances = {
        name: float(val) for name, val in zip(FEATURE_COLUMNS, model.feature_importances_)
    }

    metadata = ModelMetadata.build(
        model_name=MODEL_NAMES["adaptive_sequencing"],
        model_version="0.1.0",
        framework="xgboost",
        metrics={"rmse": rmse, "r2": r2, "map_at_5": map5},
        stage="Staging",
    )

    artifact_path = Path(artifact_dir)
    write_local_artifact_bundle(
        artifact_path,
        model_obj=model,
        metadata=metadata,
        feature_names=FEATURE_COLUMNS,
        extras={"feature_importances": importances},
    )

    run_id = None
    model_version = metadata.model_version
    if register:
        configure_mlflow(experiment_name="asiwdp-adaptive-sequencing")
        try:
            run_id, model_version = log_and_register_model(
                model_name=MODEL_NAMES["adaptive_sequencing"],
                artifact_path="model",
                registered_model_name=MODEL_NAMES["adaptive_sequencing"],
                metrics={"rmse": rmse, "r2": r2, "map_at_5": map5},
                params={"n_estimators": 80, "max_depth": 4, "n_learners": n_learners},
                metadata=metadata,
                tags={"model_family": "adaptive_sequencing"},
                flavor="xgboost",
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
        "rmse": rmse,
        "r2": r2,
        "map_at_5": map5,
        "artifact_dir": str(artifact_path),
        "mlflow_run_id": run_id,
        "model_version": model_version,
        "metadata": metadata.to_dict(),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Train ASIWDP adaptive sequencing model")
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))
    parser.add_argument("--n-learners", type=int, default=250)
    parser.add_argument("--no-register", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    result = train_adaptive_sequencing_model(
        artifact_dir=args.artifact_dir,
        register=not args.no_register,
        n_learners=args.n_learners,
        seed=args.seed,
    )
    print(json.dumps({k: v for k, v in result.items() if k != "metadata"}, indent=2))


if __name__ == "__main__":
    main()
