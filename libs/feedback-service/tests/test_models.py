"""Tests for Feedback models and validation."""

import pytest
from uuid import uuid4
from datetime import datetime

from pydantic import ValidationError

from feedback_service.models import (
    Feedback,
    FeedbackCreate,
    FeedbackResponse,
    FeedbackType,
)


class TestFeedbackType:
    """Tests for FeedbackType enum."""

    def test_accept_value(self):
        assert FeedbackType.ACCEPT.value == "accept"

    def test_reject_value(self):
        assert FeedbackType.REJECT.value == "reject"

    def test_from_string_accept(self):
        assert FeedbackType("accept") == FeedbackType.ACCEPT

    def test_from_string_reject(self):
        assert FeedbackType("reject") == FeedbackType.REJECT

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError):
            FeedbackType("invalid")


class TestFeedbackCreate:
    """Tests for FeedbackCreate schema validation."""

    def test_valid_accept_feedback(self, recommendation_id):
        feedback = FeedbackCreate(
            recommendation_id=recommendation_id,
            feedback_type=FeedbackType.ACCEPT,
            rating=5,
            comment="Great recommendation!",
        )
        assert feedback.recommendation_id == recommendation_id
        assert feedback.feedback_type == FeedbackType.ACCEPT
        assert feedback.rating == 5
        assert feedback.comment == "Great recommendation!"

    def test_valid_reject_feedback(self, recommendation_id):
        feedback = FeedbackCreate(
            recommendation_id=recommendation_id,
            feedback_type=FeedbackType.REJECT,
        )
        assert feedback.feedback_type == FeedbackType.REJECT
        assert feedback.rating is None
        assert feedback.comment is None

    def test_minimal_feedback(self, recommendation_id):
        """Test feedback with only required fields."""
        feedback = FeedbackCreate(
            recommendation_id=recommendation_id,
            feedback_type=FeedbackType.ACCEPT,
        )
        assert feedback.rating is None
        assert feedback.comment is None

    def test_rating_min_boundary(self, recommendation_id):
        """Test rating at minimum value (1)."""
        feedback = FeedbackCreate(
            recommendation_id=recommendation_id,
            feedback_type=FeedbackType.ACCEPT,
            rating=1,
        )
        assert feedback.rating == 1

    def test_rating_max_boundary(self, recommendation_id):
        """Test rating at maximum value (5)."""
        feedback = FeedbackCreate(
            recommendation_id=recommendation_id,
            feedback_type=FeedbackType.ACCEPT,
            rating=5,
        )
        assert feedback.rating == 5

    def test_rating_below_min_raises(self, recommendation_id):
        """Test that rating below 1 raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            FeedbackCreate(
                recommendation_id=recommendation_id,
                feedback_type=FeedbackType.ACCEPT,
                rating=0,
            )
        assert "rating" in str(exc_info.value).lower()

    def test_rating_above_max_raises(self, recommendation_id):
        """Test that rating above 5 raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            FeedbackCreate(
                recommendation_id=recommendation_id,
                feedback_type=FeedbackType.ACCEPT,
                rating=6,
            )
        assert "rating" in str(exc_info.value).lower()

    def test_missing_recommendation_id_raises(self):
        """Test that missing recommendation_id raises validation error."""
        with pytest.raises(ValidationError):
            FeedbackCreate(feedback_type=FeedbackType.ACCEPT)

    def test_missing_feedback_type_raises(self, recommendation_id):
        """Test that missing feedback_type raises validation error."""
        with pytest.raises(ValidationError):
            FeedbackCreate(recommendation_id=recommendation_id)

    def test_comment_max_length(self, recommendation_id):
        """Test that comment respects max length of 2000."""
        long_comment = "x" * 2000
        feedback = FeedbackCreate(
            recommendation_id=recommendation_id,
            feedback_type=FeedbackType.ACCEPT,
            comment=long_comment,
        )
        assert len(feedback.comment) == 2000

    def test_comment_exceeds_max_length_raises(self, recommendation_id):
        """Test that comment over 2000 chars raises validation error."""
        too_long_comment = "x" * 2001
        with pytest.raises(ValidationError) as exc_info:
            FeedbackCreate(
                recommendation_id=recommendation_id,
                feedback_type=FeedbackType.ACCEPT,
                comment=too_long_comment,
            )
        assert "comment" in str(exc_info.value).lower()


class TestFeedback:
    """Tests for Feedback entity model."""

    def test_feedback_creation(self, tenant_id, learner_id, recommendation_id):
        feedback = Feedback(
            tenant_id=tenant_id,
            learner_id=learner_id,
            recommendation_id=recommendation_id,
            feedback_type=FeedbackType.ACCEPT,
            rating=4,
            comment="Helpful suggestion",
            model_version="v1.2.0",
        )
        assert feedback.id is not None
        assert feedback.tenant_id == tenant_id
        assert feedback.learner_id == learner_id
        assert feedback.recommendation_id == recommendation_id
        assert feedback.feedback_type == FeedbackType.ACCEPT
        assert feedback.rating == 4
        assert feedback.comment == "Helpful suggestion"
        assert feedback.model_version == "v1.2.0"
        assert isinstance(feedback.created_at, datetime)

    def test_feedback_auto_generates_id(self, tenant_id, learner_id, recommendation_id):
        feedback = Feedback(
            tenant_id=tenant_id,
            learner_id=learner_id,
            recommendation_id=recommendation_id,
            feedback_type=FeedbackType.REJECT,
        )
        assert feedback.id is not None

    def test_feedback_auto_generates_timestamp(
        self, tenant_id, learner_id, recommendation_id
    ):
        before = datetime.utcnow()
        feedback = Feedback(
            tenant_id=tenant_id,
            learner_id=learner_id,
            recommendation_id=recommendation_id,
            feedback_type=FeedbackType.ACCEPT,
        )
        after = datetime.utcnow()
        assert before <= feedback.created_at <= after


class TestFeedbackResponse:
    """Tests for FeedbackResponse schema."""

    def test_response_from_feedback(self, tenant_id, learner_id, recommendation_id):
        feedback = Feedback(
            tenant_id=tenant_id,
            learner_id=learner_id,
            recommendation_id=recommendation_id,
            feedback_type=FeedbackType.ACCEPT,
            rating=5,
        )
        response = FeedbackResponse(
            id=feedback.id,
            tenant_id=feedback.tenant_id,
            learner_id=feedback.learner_id,
            recommendation_id=feedback.recommendation_id,
            feedback_type=feedback.feedback_type,
            rating=feedback.rating,
            comment=feedback.comment,
            created_at=feedback.created_at,
            model_version=feedback.model_version,
        )
        assert response.id == feedback.id
        assert response.feedback_type == FeedbackType.ACCEPT

    def test_response_json_serialization(
        self, tenant_id, learner_id, recommendation_id
    ):
        response = FeedbackResponse(
            id=uuid4(),
            tenant_id=tenant_id,
            learner_id=learner_id,
            recommendation_id=recommendation_id,
            feedback_type=FeedbackType.REJECT,
            rating=None,
            comment=None,
            created_at=datetime.utcnow(),
            model_version="v1.0.0",
        )
        json_data = response.model_dump(mode="json")
        assert "id" in json_data
        assert json_data["feedback_type"] == "reject"
        assert json_data["model_version"] == "v1.0.0"
