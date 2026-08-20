"""Database repository for storing bias evaluation results.

This module provides persistence layer for bias metrics in PostgreSQL,
enabling audit trails and historical analysis.
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional
from uuid import UUID

from model_monitoring.bias_evaluator import BiasEvaluationResult, FairnessMetrics
from model_monitoring.config import BiasMonitoringConfig

logger = logging.getLogger(__name__)

# SQL for creating the monitoring tables
CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS bias_evaluation_results (
    evaluation_id UUID PRIMARY KEY,
    model_name VARCHAR(255) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    evaluation_timestamp TIMESTAMPTZ NOT NULL,
    bias_index NUMERIC(10, 6) NOT NULL,
    threshold_breached BOOLEAN NOT NULL,
    overall_accuracy NUMERIC(10, 6) NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fairness_metrics (
    id SERIAL PRIMARY KEY,
    evaluation_id UUID NOT NULL REFERENCES bias_evaluation_results(evaluation_id),
    attribute_name VARCHAR(100) NOT NULL,
    group_value VARCHAR(255) NOT NULL,
    sample_size INTEGER NOT NULL,
    positive_rate NUMERIC(10, 6) NOT NULL,
    true_positive_rate NUMERIC(10, 6) NOT NULL,
    false_positive_rate NUMERIC(10, 6) NOT NULL,
    demographic_parity_diff NUMERIC(10, 6) NOT NULL,
    equal_opportunity_diff NUMERIC(10, 6) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bias_eval_model_name ON bias_evaluation_results(model_name);
CREATE INDEX IF NOT EXISTS idx_bias_eval_timestamp ON bias_evaluation_results(evaluation_timestamp);
CREATE INDEX IF NOT EXISTS idx_bias_eval_threshold_breached ON bias_evaluation_results(threshold_breached);
CREATE INDEX IF NOT EXISTS idx_fairness_metrics_eval_id ON fairness_metrics(evaluation_id);
"""


class BiasMetricsRepository:
    """Repository for storing and retrieving bias evaluation metrics.

    This class handles persistence of BiasEvaluationResult objects to
    PostgreSQL for audit and historical analysis purposes.
    """

    def __init__(self, config: BiasMonitoringConfig):
        """Initialize the repository.

        Args:
            config: Bias monitoring configuration with database URL.
        """
        self.config = config
        self._connection_pool: Optional[Any] = None

    @contextmanager
    def _get_connection(self) -> Generator[Any, None, None]:
        """Get a database connection from the pool."""
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
        except ImportError:
            raise RuntimeError("psycopg2 is required but not installed")

        if not self.config.database_url:
            raise ValueError("Database URL not configured")

        conn = psycopg2.connect(self.config.database_url)
        try:
            yield conn
        finally:
            conn.close()

    def initialize_schema(self) -> None:
        """Create the database schema if it doesn't exist."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(CREATE_TABLES_SQL)
            conn.commit()
        logger.info("Bias monitoring schema initialized")

    def save_evaluation_result(self, result: BiasEvaluationResult) -> None:
        """Save a bias evaluation result to the database.

        Args:
            result: The evaluation result to persist.
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Insert main evaluation result
                cur.execute(
                    """
                    INSERT INTO bias_evaluation_results (
                        evaluation_id, model_name, model_version,
                        evaluation_timestamp, bias_index, threshold_breached,
                        overall_accuracy, metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (evaluation_id) DO UPDATE SET
                        bias_index = EXCLUDED.bias_index,
                        threshold_breached = EXCLUDED.threshold_breached,
                        overall_accuracy = EXCLUDED.overall_accuracy,
                        metadata = EXCLUDED.metadata
                    """,
                    (
                        str(result.evaluation_id),
                        result.model_name,
                        result.model_version,
                        result.timestamp,
                        result.bias_index,
                        result.threshold_breached,
                        result.overall_accuracy,
                        json.dumps(result.metadata),
                    ),
                )

                # Insert fairness metrics
                for metric in result.fairness_metrics:
                    cur.execute(
                        """
                        INSERT INTO fairness_metrics (
                            evaluation_id, attribute_name, group_value,
                            sample_size, positive_rate, true_positive_rate,
                            false_positive_rate, demographic_parity_diff,
                            equal_opportunity_diff
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            str(result.evaluation_id),
                            metric.attribute_name,
                            metric.group_value,
                            metric.sample_size,
                            metric.positive_rate,
                            metric.true_positive_rate,
                            metric.false_positive_rate,
                            metric.demographic_parity_diff,
                            metric.equal_opportunity_diff,
                        ),
                    )

            conn.commit()

        logger.info(
            f"Saved evaluation result for {result.model_name} "
            f"v{result.model_version} (id={result.evaluation_id})"
        )

    def get_latest_evaluation(
        self, model_name: str, model_version: Optional[str] = None
    ) -> Optional[BiasEvaluationResult]:
        """Get the most recent evaluation for a model.

        Args:
            model_name: Name of the model.
            model_version: Optional specific version.

        Returns:
            BiasEvaluationResult or None if not found.
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                if model_version:
                    cur.execute(
                        """
                        SELECT evaluation_id, model_name, model_version,
                               evaluation_timestamp, bias_index, threshold_breached,
                               overall_accuracy, metadata
                        FROM bias_evaluation_results
                        WHERE model_name = %s AND model_version = %s
                        ORDER BY evaluation_timestamp DESC
                        LIMIT 1
                        """,
                        (model_name, model_version),
                    )
                else:
                    cur.execute(
                        """
                        SELECT evaluation_id, model_name, model_version,
                               evaluation_timestamp, bias_index, threshold_breached,
                               overall_accuracy, metadata
                        FROM bias_evaluation_results
                        WHERE model_name = %s
                        ORDER BY evaluation_timestamp DESC
                        LIMIT 1
                        """,
                        (model_name,),
                    )

                row = cur.fetchone()
                if not row:
                    return None

                evaluation_id = UUID(row[0])

                # Fetch associated fairness metrics
                cur.execute(
                    """
                    SELECT attribute_name, group_value, sample_size,
                           positive_rate, true_positive_rate, false_positive_rate,
                           demographic_parity_diff, equal_opportunity_diff
                    FROM fairness_metrics
                    WHERE evaluation_id = %s
                    """,
                    (str(evaluation_id),),
                )

                metrics = [
                    FairnessMetrics(
                        attribute_name=m[0],
                        group_value=m[1],
                        sample_size=m[2],
                        positive_rate=float(m[3]),
                        true_positive_rate=float(m[4]),
                        false_positive_rate=float(m[5]),
                        demographic_parity_diff=float(m[6]),
                        equal_opportunity_diff=float(m[7]),
                    )
                    for m in cur.fetchall()
                ]

                return BiasEvaluationResult(
                    evaluation_id=evaluation_id,
                    model_name=row[1],
                    model_version=row[2],
                    timestamp=row[3],
                    bias_index=float(row[4]),
                    threshold_breached=row[5],
                    fairness_metrics=metrics,
                    overall_accuracy=float(row[6]),
                    metadata=row[7] or {},
                )

    def get_evaluation_history(
        self,
        model_name: str,
        limit: int = 30,
        since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Get evaluation history for a model.

        Args:
            model_name: Name of the model.
            limit: Maximum number of results.
            since: Optional start date filter.

        Returns:
            List of evaluation summaries.
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                if since:
                    cur.execute(
                        """
                        SELECT evaluation_id, model_version, evaluation_timestamp,
                               bias_index, threshold_breached, overall_accuracy
                        FROM bias_evaluation_results
                        WHERE model_name = %s AND evaluation_timestamp >= %s
                        ORDER BY evaluation_timestamp DESC
                        LIMIT %s
                        """,
                        (model_name, since, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT evaluation_id, model_version, evaluation_timestamp,
                               bias_index, threshold_breached, overall_accuracy
                        FROM bias_evaluation_results
                        WHERE model_name = %s
                        ORDER BY evaluation_timestamp DESC
                        LIMIT %s
                        """,
                        (model_name, limit),
                    )

                return [
                    {
                        "evaluation_id": row[0],
                        "model_version": row[1],
                        "timestamp": row[2],
                        "bias_index": float(row[3]),
                        "threshold_breached": row[4],
                        "overall_accuracy": float(row[5]),
                    }
                    for row in cur.fetchall()
                ]

    def get_breached_evaluations(
        self, since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get all evaluations that breached the bias threshold.

        Args:
            since: Optional start date filter.

        Returns:
            List of breached evaluation summaries.
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                if since:
                    cur.execute(
                        """
                        SELECT evaluation_id, model_name, model_version,
                               evaluation_timestamp, bias_index
                        FROM bias_evaluation_results
                        WHERE threshold_breached = TRUE AND evaluation_timestamp >= %s
                        ORDER BY evaluation_timestamp DESC
                        """,
                        (since,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT evaluation_id, model_name, model_version,
                               evaluation_timestamp, bias_index
                        FROM bias_evaluation_results
                        WHERE threshold_breached = TRUE
                        ORDER BY evaluation_timestamp DESC
                        """
                    )

                return [
                    {
                        "evaluation_id": row[0],
                        "model_name": row[1],
                        "model_version": row[2],
                        "timestamp": row[3],
                        "bias_index": float(row[4]),
                    }
                    for row in cur.fetchall()
                ]
