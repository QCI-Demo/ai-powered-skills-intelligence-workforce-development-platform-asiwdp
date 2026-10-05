"""Command-line interface for bias evaluator."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional

from asiwdp_bias.config import BiasConfig
from asiwdp_bias.evaluator import BiasEvaluator


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="bias-evaluator",
        description="Evaluate ML models for bias and fairness",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # evaluate command
    eval_parser = subparsers.add_parser(
        "evaluate",
        help="Run bias evaluation on models",
    )
    eval_parser.add_argument(
        "--validation-data",
        type=str,
        required=True,
        help="Path to validation data file (parquet, csv, or json)",
    )
    eval_parser.add_argument(
        "--protected-attrs",
        type=str,
        default=None,
        help="Comma-separated list of protected attribute columns",
    )
    eval_parser.add_argument(
        "--target-column",
        type=str,
        default="target",
        help="Name of target/label column (default: target)",
    )
    eval_parser.add_argument(
        "--model-name",
        type=str,
        default=None,
        help="Specific model name to evaluate (default: all)",
    )
    eval_parser.add_argument(
        "--model-version",
        type=str,
        default=None,
        help="Specific model version to evaluate",
    )
    eval_parser.add_argument(
        "--stages",
        type=str,
        default=None,
        help="Comma-separated list of stages to evaluate (e.g., Production,Staging)",
    )
    eval_parser.add_argument(
        "--tenant-id",
        type=str,
        default=None,
        help="Tenant ID for multi-tenant deployments",
    )
    eval_parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Override bias threshold (default: 0.05)",
    )
    eval_parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file for results (json format)",
    )
    eval_parser.add_argument(
        "--report-format",
        choices=["text", "markdown", "json"],
        default="text",
        help="Report output format (default: text)",
    )
    eval_parser.add_argument(
        "--no-store",
        action="store_true",
        help="Skip storing results to database",
    )
    
    # check command (for CI/CD gate)
    check_parser = subparsers.add_parser(
        "check",
        help="Check if a model passes fairness gate (for CI/CD)",
    )
    check_parser.add_argument(
        "--validation-data",
        type=str,
        required=True,
        help="Path to validation data file",
    )
    check_parser.add_argument(
        "--model-name",
        type=str,
        required=True,
        help="Model name to check",
    )
    check_parser.add_argument(
        "--model-version",
        type=str,
        required=True,
        help="Model version to check",
    )
    check_parser.add_argument(
        "--protected-attrs",
        type=str,
        default=None,
        help="Comma-separated list of protected attribute columns",
    )
    check_parser.add_argument(
        "--target-column",
        type=str,
        default="target",
        help="Name of target/label column",
    )
    check_parser.add_argument(
        "--tenant-id",
        type=str,
        default=None,
        help="Tenant ID",
    )
    check_parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Override bias threshold",
    )
    
    # init-db command
    init_parser = subparsers.add_parser(
        "init-db",
        help="Initialize database schema",
    )
    
    return parser.parse_args()


def cmd_evaluate(args: argparse.Namespace, config: BiasConfig) -> int:
    """Run evaluation command."""
    logger = logging.getLogger(__name__)
    
    evaluator = BiasEvaluator(config)
    
    # Parse protected attributes
    protected_attrs = None
    if args.protected_attrs:
        protected_attrs = [a.strip() for a in args.protected_attrs.split(",")]
    
    # Parse stages
    stages = None
    if args.stages:
        stages = [s.strip() for s in args.stages.split(",")]
    
    # Parse model names
    model_names = None
    if args.model_name:
        model_names = [args.model_name]
    
    # Run evaluation
    try:
        results = evaluator.evaluate_all_models(
            validation_data_path=args.validation_data,
            protected_attributes=protected_attrs,
            target_column=args.target_column,
            stages=stages,
            model_names=model_names,
            tenant_id=args.tenant_id,
            store_results=not args.no_store,
        )
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        return 1
    
    if not results:
        logger.warning("No models were evaluated")
        return 0
    
    # Output results
    if args.report_format == "json":
        output = [r.model_dump(mode="json") for r in results]
        print(json.dumps(output, indent=2, default=str))
    else:
        for result in results:
            report = evaluator.generate_report(
                result,
                output_format=args.report_format,
            )
            print(report)
            print()
    
    # Write to output file if specified
    if args.output:
        output_path = Path(args.output)
        output_data = [r.model_dump(mode="json") for r in results]
        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2, default=str)
        logger.info(f"Results written to {output_path}")
    
    # Return non-zero if any model failed
    failed = sum(1 for r in results if r.threshold_breached)
    if failed > 0:
        logger.warning(f"{failed} model(s) failed bias threshold check")
        return 1
    
    return 0


def cmd_check(args: argparse.Namespace, config: BiasConfig) -> int:
    """Run check command for CI/CD gate."""
    logger = logging.getLogger(__name__)
    
    evaluator = BiasEvaluator(config)
    
    # Parse protected attributes
    protected_attrs = None
    if args.protected_attrs:
        protected_attrs = [a.strip() for a in args.protected_attrs.split(",")]
    
    try:
        passed, result = evaluator.check_model_promotion_gate(
            model_name=args.model_name,
            model_version=args.model_version,
            validation_data_path=args.validation_data,
            protected_attributes=protected_attrs,
            target_column=args.target_column,
            tenant_id=args.tenant_id,
        )
    except Exception as e:
        logger.error(f"Check failed: {e}")
        return 1
    
    # Print report
    report = evaluator.generate_report(result, output_format="text")
    print(report)
    
    if passed:
        print(f"\n✅ Model {args.model_name} v{args.model_version} PASSED fairness gate")
        return 0
    else:
        print(f"\n❌ Model {args.model_name} v{args.model_version} FAILED fairness gate")
        print(f"   Bias index: {result.overall_bias_index:.4f} > threshold: {config.threshold}")
        return 1


def cmd_init_db(args: argparse.Namespace, config: BiasConfig) -> int:
    """Initialize database schema."""
    logger = logging.getLogger(__name__)
    
    from asiwdp_bias.storage import BiasResultStorage
    
    storage = BiasResultStorage(config)
    try:
        storage.initialize_schema()
        logger.info("Database schema initialized successfully")
        return 0
    except Exception as e:
        logger.error(f"Failed to initialize schema: {e}")
        return 1


def main() -> int:
    """Main entry point."""
    args = parse_args()
    setup_logging(args.verbose)
    
    # Build config
    config = BiasConfig.from_env()
    
    # Override threshold if specified
    if hasattr(args, "threshold") and args.threshold is not None:
        config.threshold = args.threshold
    
    # Dispatch command
    if args.command == "evaluate":
        return cmd_evaluate(args, config)
    elif args.command == "check":
        return cmd_check(args, config)
    elif args.command == "init-db":
        return cmd_init_db(args, config)
    else:
        print("Please specify a command. Use --help for usage.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
