"""Data models for bias evaluation results."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class GroupMetrics(BaseModel):
    """Fairness metrics for a specific demographic group."""

    group_name: str = Field(..., description="Name/value of the demographic group")
    sample_count: int = Field(..., ge=0, description="Number of samples in this group")
    positive_rate: float = Field(
        ..., ge=0.0, le=1.0, description="Rate of positive predictions"
    )
    true_positive_rate: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="True positive rate (recall)"
    )
    false_positive_rate: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="False positive rate"
    )
    true_negative_rate: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="True negative rate (specificity)"
    )
    false_negative_rate: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="False negative rate"
    )
    precision: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Precision for this group"
    )
    accuracy: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Accuracy for this group"
    )


class AttributeEvaluation(BaseModel):
    """Evaluation results for a single protected attribute."""

    attribute_name: str = Field(..., description="Name of the protected attribute")
    group_metrics: list[GroupMetrics] = Field(
        default_factory=list, description="Metrics for each group"
    )
    demographic_parity_diff: float = Field(
        ..., ge=0.0, description="Demographic parity difference"
    )
    equal_opportunity_diff: Optional[float] = Field(
        default=None, ge=0.0, description="Equal opportunity difference"
    )
    equalized_odds_diff: Optional[float] = Field(
        default=None, ge=0.0, description="Equalized odds difference"
    )
    bias_index: float = Field(
        ..., ge=0.0, le=1.0, description="Aggregated bias index for this attribute"
    )


class BiasEvaluationResult(BaseModel):
    """Complete bias evaluation result for a model."""

    id: UUID = Field(default_factory=uuid4, description="Unique evaluation ID")
    model_name: str = Field(..., description="Name of the evaluated model")
    model_version: str = Field(..., description="Version of the evaluated model")
    model_stage: Optional[str] = Field(
        default=None, description="MLflow stage (None, Staging, Production, Archived)"
    )
    evaluation_timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When evaluation was performed"
    )
    
    # Overall results
    overall_bias_index: float = Field(
        ..., ge=0.0, le=1.0, description="Aggregated bias index across all attributes"
    )
    threshold: float = Field(..., description="Bias threshold used for evaluation")
    threshold_breached: bool = Field(
        ..., description="Whether bias index exceeds threshold"
    )
    
    # Per-attribute results
    attribute_evaluations: list[AttributeEvaluation] = Field(
        default_factory=list, description="Evaluation results per protected attribute"
    )
    
    # Metadata
    total_samples: int = Field(..., ge=0, description="Total samples in validation set")
    protected_attributes: list[str] = Field(
        ..., description="List of protected attributes evaluated"
    )
    tenant_id: Optional[str] = Field(
        default=None, description="Tenant ID for multi-tenant deployments"
    )
    run_id: Optional[str] = Field(
        default=None, description="MLflow run ID if applicable"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional evaluation metadata"
    )

    def is_passing(self) -> bool:
        """Check if the model passes fairness criteria."""
        return not self.threshold_breached

    def get_worst_attribute(self) -> Optional[AttributeEvaluation]:
        """Return the protected attribute with highest bias index."""
        if not self.attribute_evaluations:
            return None
        return max(self.attribute_evaluations, key=lambda x: x.bias_index)


class ModelEndpoint(BaseModel):
    """MLflow model endpoint information."""

    name: str = Field(..., description="Model name in registry")
    version: str = Field(..., description="Model version")
    stage: Optional[str] = Field(default=None, description="Model stage")
    run_id: Optional[str] = Field(default=None, description="Associated run ID")
    source: Optional[str] = Field(default=None, description="Model artifact URI")
    description: Optional[str] = Field(default=None, description="Model description")
    tags: dict[str, str] = Field(default_factory=dict, description="Model tags")

    @property
    def model_uri(self) -> str:
        """Return MLflow model URI."""
        return f"models:/{self.name}/{self.version}"
