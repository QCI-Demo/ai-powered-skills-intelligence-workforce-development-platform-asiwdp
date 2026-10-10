"""Tests for FeedbackRepository storage and retrieval."""

import pytest
from uuid import uuid4

from feedback_service.models import FeedbackCreate, FeedbackType
from feedback_service.repository import FeedbackRepository


class TestFeedbackRepositoryCreate:
    """Tests for creating feedback entries."""

    def test_create_feedback(self, repository, tenant_id, learner_id, recommendation_id):
        feedback_data = FeedbackCreate(
            recommendation_id=recommendation_id,
            feedback_type=FeedbackType.ACCEPT,
            rating=5,
            comment="Excellent!",
        )
        feedback = repository.create(
            tenant_id=tenant_id,
            learner_id=learner_id,
            feedback_data=feedback_data,
            model_version="v1.0.0",
        )

        assert feedback.id is not None
        assert feedback.tenant_id == tenant_id
        assert feedback.learner_id == learner_id
        assert feedback.recommendation_id == recommendation_id
        assert feedback.feedback_type == FeedbackType.ACCEPT
        assert feedback.rating == 5
        assert feedback.comment == "Excellent!"
        assert feedback.model_version == "v1.0.0"

    def test_create_minimal_feedback(
        self, repository, tenant_id, learner_id, recommendation_id
    ):
        feedback_data = FeedbackCreate(
            recommendation_id=recommendation_id,
            feedback_type=FeedbackType.REJECT,
        )
        feedback = repository.create(
            tenant_id=tenant_id,
            learner_id=learner_id,
            feedback_data=feedback_data,
        )

        assert feedback.rating is None
        assert feedback.comment is None
        assert feedback.model_version is None


class TestFeedbackRepositoryRetrieve:
    """Tests for retrieving feedback entries."""

    def test_get_by_id_success(
        self, repository, tenant_id, learner_id, recommendation_id
    ):
        feedback_data = FeedbackCreate(
            recommendation_id=recommendation_id,
            feedback_type=FeedbackType.ACCEPT,
        )
        created = repository.create(tenant_id, learner_id, feedback_data)

        retrieved = repository.get_by_id(created.id, tenant_id)
        assert retrieved is not None
        assert retrieved.id == created.id

    def test_get_by_id_wrong_tenant_returns_none(
        self, repository, tenant_id, learner_id, recommendation_id
    ):
        feedback_data = FeedbackCreate(
            recommendation_id=recommendation_id,
            feedback_type=FeedbackType.ACCEPT,
        )
        created = repository.create(tenant_id, learner_id, feedback_data)

        other_tenant = uuid4()
        retrieved = repository.get_by_id(created.id, other_tenant)
        assert retrieved is None

    def test_get_by_id_not_found(self, repository, tenant_id):
        retrieved = repository.get_by_id(uuid4(), tenant_id)
        assert retrieved is None

    def test_get_by_recommendation(
        self, repository, tenant_id, learner_id, recommendation_id
    ):
        # Create multiple feedback for same recommendation
        for i in range(3):
            feedback_data = FeedbackCreate(
                recommendation_id=recommendation_id,
                feedback_type=FeedbackType.ACCEPT,
                rating=i + 1,
            )
            repository.create(tenant_id, learner_id, feedback_data)

        # Create one for different recommendation
        other_rec = uuid4()
        feedback_data = FeedbackCreate(
            recommendation_id=other_rec,
            feedback_type=FeedbackType.REJECT,
        )
        repository.create(tenant_id, learner_id, feedback_data)

        results = repository.get_by_recommendation(recommendation_id, tenant_id)
        assert len(results) == 3

    def test_get_by_recommendation_tenant_isolation(
        self, repository, tenant_id, learner_id, recommendation_id
    ):
        feedback_data = FeedbackCreate(
            recommendation_id=recommendation_id,
            feedback_type=FeedbackType.ACCEPT,
        )
        repository.create(tenant_id, learner_id, feedback_data)

        other_tenant = uuid4()
        results = repository.get_by_recommendation(recommendation_id, other_tenant)
        assert len(results) == 0

    def test_get_by_learner(self, repository, tenant_id, learner_id):
        # Create feedback from our learner
        for _ in range(2):
            feedback_data = FeedbackCreate(
                recommendation_id=uuid4(),
                feedback_type=FeedbackType.ACCEPT,
            )
            repository.create(tenant_id, learner_id, feedback_data)

        # Create feedback from another learner
        other_learner = uuid4()
        feedback_data = FeedbackCreate(
            recommendation_id=uuid4(),
            feedback_type=FeedbackType.REJECT,
        )
        repository.create(tenant_id, other_learner, feedback_data)

        results = repository.get_by_learner(learner_id, tenant_id)
        assert len(results) == 2


class TestFeedbackRepositoryList:
    """Tests for listing feedback entries."""

    def test_list_by_tenant(self, repository, tenant_id, learner_id):
        for i in range(5):
            feedback_data = FeedbackCreate(
                recommendation_id=uuid4(),
                feedback_type=FeedbackType.ACCEPT if i % 2 == 0 else FeedbackType.REJECT,
            )
            repository.create(tenant_id, learner_id, feedback_data)

        results = repository.list_by_tenant(tenant_id)
        assert len(results) == 5

    def test_list_by_tenant_with_type_filter(self, repository, tenant_id, learner_id):
        for i in range(5):
            feedback_data = FeedbackCreate(
                recommendation_id=uuid4(),
                feedback_type=FeedbackType.ACCEPT if i % 2 == 0 else FeedbackType.REJECT,
            )
            repository.create(tenant_id, learner_id, feedback_data)

        accepts = repository.list_by_tenant(tenant_id, feedback_type=FeedbackType.ACCEPT)
        rejects = repository.list_by_tenant(tenant_id, feedback_type=FeedbackType.REJECT)

        assert len(accepts) == 3  # indices 0, 2, 4
        assert len(rejects) == 2  # indices 1, 3

    def test_list_by_tenant_pagination(self, repository, tenant_id, learner_id):
        for _ in range(10):
            feedback_data = FeedbackCreate(
                recommendation_id=uuid4(),
                feedback_type=FeedbackType.ACCEPT,
            )
            repository.create(tenant_id, learner_id, feedback_data)

        page1 = repository.list_by_tenant(tenant_id, limit=3, offset=0)
        page2 = repository.list_by_tenant(tenant_id, limit=3, offset=3)
        page3 = repository.list_by_tenant(tenant_id, limit=3, offset=6)
        page4 = repository.list_by_tenant(tenant_id, limit=3, offset=9)

        assert len(page1) == 3
        assert len(page2) == 3
        assert len(page3) == 3
        assert len(page4) == 1

    def test_list_by_tenant_isolation(self, repository, learner_id):
        tenant1 = uuid4()
        tenant2 = uuid4()

        for _ in range(3):
            feedback_data = FeedbackCreate(
                recommendation_id=uuid4(),
                feedback_type=FeedbackType.ACCEPT,
            )
            repository.create(tenant1, learner_id, feedback_data)

        for _ in range(2):
            feedback_data = FeedbackCreate(
                recommendation_id=uuid4(),
                feedback_type=FeedbackType.REJECT,
            )
            repository.create(tenant2, learner_id, feedback_data)

        results1 = repository.list_by_tenant(tenant1)
        results2 = repository.list_by_tenant(tenant2)

        assert len(results1) == 3
        assert len(results2) == 2

    def test_count_by_tenant(self, repository, tenant_id, learner_id):
        for _ in range(7):
            feedback_data = FeedbackCreate(
                recommendation_id=uuid4(),
                feedback_type=FeedbackType.ACCEPT,
            )
            repository.create(tenant_id, learner_id, feedback_data)

        count = repository.count_by_tenant(tenant_id)
        assert count == 7


class TestFeedbackRepositoryDelete:
    """Tests for deleting feedback entries."""

    def test_delete_success(self, repository, tenant_id, learner_id, recommendation_id):
        feedback_data = FeedbackCreate(
            recommendation_id=recommendation_id,
            feedback_type=FeedbackType.ACCEPT,
        )
        created = repository.create(tenant_id, learner_id, feedback_data)

        result = repository.delete(created.id, tenant_id)
        assert result is True

        retrieved = repository.get_by_id(created.id, tenant_id)
        assert retrieved is None

    def test_delete_wrong_tenant_fails(
        self, repository, tenant_id, learner_id, recommendation_id
    ):
        feedback_data = FeedbackCreate(
            recommendation_id=recommendation_id,
            feedback_type=FeedbackType.ACCEPT,
        )
        created = repository.create(tenant_id, learner_id, feedback_data)

        other_tenant = uuid4()
        result = repository.delete(created.id, other_tenant)
        assert result is False

        # Original should still exist
        retrieved = repository.get_by_id(created.id, tenant_id)
        assert retrieved is not None

    def test_delete_not_found(self, repository, tenant_id):
        result = repository.delete(uuid4(), tenant_id)
        assert result is False

    def test_clear_tenant(self, repository, learner_id):
        tenant1 = uuid4()
        tenant2 = uuid4()

        for _ in range(5):
            feedback_data = FeedbackCreate(
                recommendation_id=uuid4(),
                feedback_type=FeedbackType.ACCEPT,
            )
            repository.create(tenant1, learner_id, feedback_data)

        for _ in range(3):
            feedback_data = FeedbackCreate(
                recommendation_id=uuid4(),
                feedback_type=FeedbackType.REJECT,
            )
            repository.create(tenant2, learner_id, feedback_data)

        deleted = repository.clear_tenant(tenant1)
        assert deleted == 5

        assert repository.count_by_tenant(tenant1) == 0
        assert repository.count_by_tenant(tenant2) == 3
