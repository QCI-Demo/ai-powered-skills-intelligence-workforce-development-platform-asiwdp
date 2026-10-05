"""PostgreSQL storage for bias evaluation results."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from asiwdp_bias.config import BiasConfig
from asiwdp_bias.models import BiasEvaluationResult

logger = logging.getLogger(__name__)


def get_evaluation_table(metadata: MetaData, schema: str = "public") -> Table:
    """Define the model_bias_evaluations table schema."""
    return Table(
        "model_bias_evaluations",
        metadata,
        Column("id", PG_UUID(as_uuid=True), primary_key=True),
        Column("model_name", String(255), nullable=False, index=True),
        Column("model_version", String(50), nullable=False),
        Column("model_stage", String(50), nullable=True),
        Column("evaluation_timestamp", DateTime(timezone=True), nullable=False, index=True),
        Column("overall_bias_index", Float, nullable=False),
        Column("threshold", Float, nullable=False),
        Column("threshold_breached", Boolean, nullable=False, index=True),
        Column("total_samples", Integer, nullable=False),
        Column("protected_attributes", JSONB, nullable=False),
        Column("attribute_evaluations", JSONB, nullable=False),
        Column("tenant_id", String(100), nullable=True, index=True),
        Column("run_id", String(100), nullable=True),
        Column("metadata", JSONB, nullable=True),
        Column("created_at", DateTime(timezone=True), server_default=text("NOW()")),
        schema=schema,
    )


class BiasResultStorage:
    """PostgreSQL storage backend for bias evaluation results."""

    def __init__(self, config: BiasConfig):
        """Initialize storage with configuration.
        
        Args:
            config: BiasConfig with database connection settings
        """
        self.config = config
        self._engine: Optional[Engine] = None
        self._metadata = MetaData()
        self._table = get_evaluation_table(self._metadata, config.db_schema)

    @property
    def engine(self) -> Engine:
        """Lazy-initialized SQLAlchemy engine."""
        if self._engine is None:
            self._engine = create_engine(
                self.config.database_url,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
            )
        return self._engine

    def initialize_schema(self) -> None:
        """Create the evaluation table if it doesn't exist."""
        try:
            self._metadata.create_all(self.engine)
            logger.info("Bias evaluation schema initialized successfully")
        except SQLAlchemyError as e:
            logger.error(f"Failed to initialize schema: {e}")
            raise

    def store_result(self, result: BiasEvaluationResult) -> UUID:
        """Store a bias evaluation result.
        
        Args:
            result: BiasEvaluationResult to store
            
        Returns:
            UUID of the stored record
        """
        try:
            # Convert pydantic models to JSON-serializable dicts
            attr_evals = [
                {
                    "attribute_name": ae.attribute_name,
                    "demographic_parity_diff": ae.demographic_parity_diff,
                    "equal_opportunity_diff": ae.equal_opportunity_diff,
                    "equalized_odds_diff": ae.equalized_odds_diff,
                    "bias_index": ae.bias_index,
                    "group_metrics": [gm.model_dump() for gm in ae.group_metrics],
                }
                for ae in result.attribute_evaluations
            ]

            with self.engine.begin() as conn:
                conn.execute(
                    self._table.insert().values(
                        id=result.id,
                        model_name=result.model_name,
                        model_version=result.model_version,
                        model_stage=result.model_stage,
                        evaluation_timestamp=result.evaluation_timestamp,
                        overall_bias_index=result.overall_bias_index,
                        threshold=result.threshold,
                        threshold_breached=result.threshold_breached,
                        total_samples=result.total_samples,
                        protected_attributes=result.protected_attributes,
                        attribute_evaluations=attr_evals,
                        tenant_id=result.tenant_id,
                        run_id=result.run_id,
                        metadata=result.metadata,
                    )
                )
            logger.info(f"Stored evaluation result {result.id} for model {result.model_name}")
            return result.id
        except SQLAlchemyError as e:
            logger.error(f"Failed to store evaluation result: {e}")
            raise

    def get_result(self, result_id: UUID) -> Optional[BiasEvaluationResult]:
        """Retrieve a bias evaluation result by ID.
        
        Args:
            result_id: UUID of the evaluation result
            
        Returns:
            BiasEvaluationResult or None if not found
        """
        try:
            with self.engine.connect() as conn:
                row = conn.execute(
                    self._table.select().where(self._table.c.id == result_id)
                ).fetchone()
                
            if row is None:
                return None
            return self._row_to_result(row)
        except SQLAlchemyError as e:
            logger.error(f"Failed to retrieve result {result_id}: {e}")
            raise

    def get_latest_result(
        self,
        model_name: str,
        model_version: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[BiasEvaluationResult]:
        """Get the most recent evaluation for a model.
        
        Args:
            model_name: Name of the model
            model_version: Optional version filter
            tenant_id: Optional tenant filter
            
        Returns:
            Most recent BiasEvaluationResult or None
        """
        try:
            query = self._table.select().where(
                self._table.c.model_name == model_name
            )
            
            if model_version:
                query = query.where(self._table.c.model_version == model_version)
            if tenant_id:
                query = query.where(self._table.c.tenant_id == tenant_id)
                
            query = query.order_by(self._table.c.evaluation_timestamp.desc()).limit(1)
            
            with self.engine.connect() as conn:
                row = conn.execute(query).fetchone()
                
            if row is None:
                return None
            return self._row_to_result(row)
        except SQLAlchemyError as e:
            logger.error(f"Failed to get latest result for {model_name}: {e}")
            raise

    def get_breached_evaluations(
        self,
        since: Optional[datetime] = None,
        tenant_id: Optional[str] = None,
    ) -> list[BiasEvaluationResult]:
        """Get all evaluations that breached the bias threshold.
        
        Args:
            since: Optional datetime to filter from
            tenant_id: Optional tenant filter
            
        Returns:
            List of BiasEvaluationResult with threshold breaches
        """
        try:
            query = self._table.select().where(
                self._table.c.threshold_breached == True  # noqa: E712
            )
            
            if since:
                query = query.where(self._table.c.evaluation_timestamp >= since)
            if tenant_id:
                query = query.where(self._table.c.tenant_id == tenant_id)
                
            query = query.order_by(self._table.c.evaluation_timestamp.desc())
            
            with self.engine.connect() as conn:
                rows = conn.execute(query).fetchall()
                
            return [self._row_to_result(row) for row in rows]
        except SQLAlchemyError as e:
            logger.error(f"Failed to get breached evaluations: {e}")
            raise

    def get_evaluation_history(
        self,
        model_name: str,
        limit: int = 100,
        tenant_id: Optional[str] = None,
    ) -> list[BiasEvaluationResult]:
        """Get evaluation history for a model.
        
        Args:
            model_name: Name of the model
            limit: Maximum number of results
            tenant_id: Optional tenant filter
            
        Returns:
            List of BiasEvaluationResult ordered by timestamp (newest first)
        """
        try:
            query = self._table.select().where(
                self._table.c.model_name == model_name
            )
            
            if tenant_id:
                query = query.where(self._table.c.tenant_id == tenant_id)
                
            query = query.order_by(
                self._table.c.evaluation_timestamp.desc()
            ).limit(limit)
            
            with self.engine.connect() as conn:
                rows = conn.execute(query).fetchall()
                
            return [self._row_to_result(row) for row in rows]
        except SQLAlchemyError as e:
            logger.error(f"Failed to get history for {model_name}: {e}")
            raise

    def _row_to_result(self, row) -> BiasEvaluationResult:
        """Convert database row to BiasEvaluationResult."""
        from asiwdp_bias.models import AttributeEvaluation, GroupMetrics
        
        # Reconstruct attribute evaluations from JSON
        attr_evals = []
        for ae_data in row.attribute_evaluations:
            group_metrics = [
                GroupMetrics(**gm) for gm in ae_data.get("group_metrics", [])
            ]
            attr_evals.append(
                AttributeEvaluation(
                    attribute_name=ae_data["attribute_name"],
                    demographic_parity_diff=ae_data["demographic_parity_diff"],
                    equal_opportunity_diff=ae_data.get("equal_opportunity_diff"),
                    equalized_odds_diff=ae_data.get("equalized_odds_diff"),
                    bias_index=ae_data["bias_index"],
                    group_metrics=group_metrics,
                )
            )
        
        return BiasEvaluationResult(
            id=row.id,
            model_name=row.model_name,
            model_version=row.model_version,
            model_stage=row.model_stage,
            evaluation_timestamp=row.evaluation_timestamp,
            overall_bias_index=row.overall_bias_index,
            threshold=row.threshold,
            threshold_breached=row.threshold_breached,
            total_samples=row.total_samples,
            protected_attributes=row.protected_attributes,
            attribute_evaluations=attr_evals,
            tenant_id=row.tenant_id,
            run_id=row.run_id,
            metadata=row.metadata or {},
        )
