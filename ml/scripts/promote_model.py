#!/usr/bin/env python3
"""Promote a registered MLflow model version from Staging to Production."""

from __future__ import annotations

import argparse
import json
import os
import sys

from asiwdp_ml.common.metadata import MODEL_NAMES
from asiwdp_ml.common.registry import configure_mlflow, promote_model_stage


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Promote ASIWDP model Staging → Production")
    parser.add_argument(
        "--model",
        required=True,
        choices=sorted(MODEL_NAMES.keys()),
        help="Logical model family key",
    )
    parser.add_argument("--version", required=True, help="Registered model version number")
    parser.add_argument("--stage", default="Production")
    parser.add_argument("--tracking-uri", default=os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db"))
    args = parser.parse_args(argv)

    configure_mlflow(tracking_uri=args.tracking_uri)
    name = MODEL_NAMES[args.model]
    promote_model_stage(name, args.version, stage=args.stage)
    print(json.dumps({"model": name, "version": args.version, "stage": args.stage}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
