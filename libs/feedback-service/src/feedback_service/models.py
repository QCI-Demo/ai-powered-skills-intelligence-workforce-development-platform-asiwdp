"""Feedback entity models and schemas."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class FeedbackType(str, Enum):
    """Type of feedback action."""

    ACCEPT = "accept"
    REJECT = "reject"


class FeedbackCreate(BaseModel):
    """Schema for creating new feedback (request body)."""

    recommendation_id: UUID = Field(
        ..., description="ID of the recommendation being reviewed"
    )
    feedback_type: FeedbackType = Field(
        ..., description="Whether learner accepted or rejected the recommendation"
    )
    rating: Optional[int] = Field(
        None,
        ge=1,
        le=5,
        description="Optional rating from 1 to 5",
    )
    comment: Optional[str] = Field(
        None, max_length=2000, description="Optional learner comment"
    )

    @field_validator("rating")
    @classmethod
    def validate_rating_range(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 1 or v > 5):
            raise ValueError("Rating must be between 1 and 5")
        return v


class Feedback(BaseModel):
    """
    Feedback entity representing learner feedback on a recommendation.

    Foreign keys:
    - recommendation_id: References recommendation record
    - tenant_id: Tenant scope for multi-tenancy isolation
    - learner_id: User who submitted the feedback
    """

    id: UUID = Field(default_factory=uuid4, description="Unique feedback ID")
    tenant_id: UUID = Field(..., description="Tenant scope (foreign key)")
    learner_id: UUID = Field(..., description="Learner user ID (foreign key)")
    recommendation_id: UUID = Field(
        ..., description="Recommendation ID (foreign key to recommendation record)"
    )
    feedback_type: FeedbackType = Field(
        ..., description="Accept or reject action"
    )
    rating: Optional[int] = Field(
        None, ge=1, le=5, description="Optional 1-5 rating"
    )
    comment: Optional[str] = Field(None, description="Optional comment")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp of submission"
    )
    model_version: Optional[str] = Field(
        None, description="Version of the recommendation model"
    )

    class Config:
        """Pydantic model configuration."""

        json_encoders = {datetime: lambda v: v.isoformat()}


class FeedbackResponse(BaseModel):
    """API response schema for feedback."""

    id: UUID
    tenant_id: UUID
    learner_id: UUID
    recommendation_id: UUID
    feedback_type: FeedbackType
    rating: Optional[int]
    comment: Optional[str]
    created_at: datetime
    model_version: Optional[str]

    class Config:
        """Pydantic model configuration."""

        from_attributes = True
        json_encoders = {datetime: lambda v: v.isoformat()}
