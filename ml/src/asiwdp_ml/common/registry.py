"""MLflow registration and stage-promotion helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import mlflow
from mlflow.tracking import MlflowClient

from asiwdp_ml.common.metadata import ModelMetadata

# XGBoost estimators are trusted for skops when logged via sklearn flavor fallback.
XGBOOST_TRUSTED_TYPES = [
    "xgboost.core.Booster",
    "xgboost.sklearn.XGBClassifier",
    "xgboost.sklearn.XGBRegressor",
]


def configure_mlflow(tracking_uri: str | None = None, experiment_name: str | None = None) -> None:
    # Prefer SQLite over legacy file store; allow file store when explicitly requested.
    default_uri = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
    uri = tracking_uri or default_uri
    if uri.startswith("file:"):
        os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
    mlflow.set_tracking_uri(uri)
    if experiment_name:
        mlflow.set_experiment(experiment_name)


def log_and_register_model(
    *,
    model_name: str,
    artifact_path: str,
    conda_env: dict[str, Any] | None = None,
    registered_model_name: str,
    metrics: dict[str, float],
    params: dict[str, Any],
    metadata: ModelMetadata,
    tags: dict[str, str] | None = None,
    flavor: str = "sklearn",
    model_obj: Any = None,
) -> tuple[str, str]:
    """Log metrics/params/artifact and register a new model version.

    Returns (run_id, model_version).
    """
    with mlflow.start_run() as run:
        mlflow.log_params({k: str(v) for k, v in params.items()})
        mlflow.log_metrics(metrics)
        mlflow.set_tags(tags or {})
        mlflow.log_dict(metadata.to_dict(), "model_metadata.json")

        log_kwargs: dict[str, Any] = {
            "registered_model_name": registered_model_name,
        }
        # Newer MLflow prefers `name` over deprecated `artifact_path`.
        try:
            if model_obj is not None and flavor == "xgboost":
                mlflow.xgboost.log_model(model_obj, name=artifact_path, **log_kwargs)
            elif model_obj is not None and flavor == "sklearn":
                mlflow.sklearn.log_model(
                    model_obj,
                    name=artifact_path,
                    skops_trusted_types=XGBOOST_TRUSTED_TYPES,
                    **log_kwargs,
                )
            else:
                local = Path(artifact_path)
                if local.exists():
                    mlflow.log_artifacts(str(local), artifact_path="model")
                mlflow.register_model(f"runs:/{run.info.run_id}/model", registered_model_name)
        except TypeError:
            # Older MLflow: fall back to artifact_path kwarg.
            if model_obj is not None and flavor == "xgboost":
                mlflow.xgboost.log_model(
                    model_obj, artifact_path=artifact_path, registered_model_name=registered_model_name
                )
            elif model_obj is not None:
                mlflow.sklearn.log_model(
                    model_obj,
                    artifact_path=artifact_path,
                    registered_model_name=registered_model_name,
                    skops_trusted_types=XGBOOST_TRUSTED_TYPES,
                )

        client = MlflowClient()
        versions = client.search_model_versions(f"name='{registered_model_name}'")
        latest = max(versions, key=lambda v: int(v.version))
        client.set_model_version_tag(
            registered_model_name, latest.version, "feature_schema_version", metadata.feature_schema_version
        )
        client.set_model_version_tag(
            registered_model_name, latest.version, "trained_at", metadata.trained_at
        )
        return run.info.run_id, str(latest.version)


def promote_model_stage(
    registered_model_name: str,
    version: str,
    stage: str = "Production",
    archive_existing: bool = True,
) -> None:
    """Promote a model version from Staging to Production (or other stage).

    Prefers MLflow Registry aliases (forward-compatible) and also transitions
    the legacy stage field when the tracking server still supports it.
    """
    client = MlflowClient()
    alias = stage.lower()
    try:
        client.set_registered_model_alias(
            name=registered_model_name,
            alias=alias,
            version=version,
        )
    except Exception:
        # Older tracking servers may not support aliases.
        pass

    try:
        client.transition_model_version_stage(
            name=registered_model_name,
            version=version,
            stage=stage,
            archive_existing_versions=archive_existing,
        )
    except Exception as exc:
        # If alias succeeded, treat stage deprecation/removal as non-fatal.
        try:
            client.get_model_version_by_alias(registered_model_name, alias)
        except Exception as alias_exc:
            raise RuntimeError(
                f"Failed to promote {registered_model_name} v{version} to {stage}"
            ) from exc
        _ = alias_exc  # alias path succeeded


def write_local_artifact_bundle(
    output_dir: str | Path,
    *,
    model_obj: Any,
    metadata: ModelMetadata,
    feature_names: list[str],
    extras: dict[str, Any] | None = None,
) -> Path:
    """Persist a portable artifact directory for Docker serving (no MLflow server required)."""
    import joblib

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    joblib.dump(model_obj, out / "model.joblib")
    (out / "metadata.json").write_text(json.dumps(metadata.to_dict(), indent=2), encoding="utf-8")
    (out / "feature_names.json").write_text(json.dumps(feature_names, indent=2), encoding="utf-8")
    if extras:
        (out / "extras.json").write_text(json.dumps(extras, indent=2, default=str), encoding="utf-8")
    return out
