"""
Feedback repository for tenant-scoped persistence.

Provides in-memory storage for demonstration; production implementations
should use a database backend (PostgreSQL, etc.).
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from feedback_service.models import Feedback, FeedbackCreate, FeedbackType


class FeedbackRepository:
    """
    Repository for storing and retrieving learner feedback.

    Implements tenant-scoped storage with foreign key relationships to
    recommendation records.
    """

    def __init__(self) -> None:
        """Initialize the repository with in-memory storage."""
        self._storage: dict[UUID, Feedback] = {}

    def create(
        self,
        tenant_id: UUID,
        learner_id: UUID,
        feedback_data: FeedbackCreate,
        model_version: Optional[str] = None,
    ) -> Feedback:
        """
        Create and store new feedback.

        Args:
            tenant_id: Tenant scope for multi-tenancy isolation
            learner_id: ID of the learner submitting feedback
            feedback_data: Feedback creation payload
            model_version: Version of the recommendation model

        Returns:
            The created Feedback entity
        """
        feedback = Feedback(
            tenant_id=tenant_id,
            learner_id=learner_id,
            recommendation_id=feedback_data.recommendation_id,
            feedback_type=feedback_data.feedback_type,
            rating=feedback_data.rating,
            comment=feedback_data.comment,
            model_version=model_version,
            created_at=datetime.utcnow(),
        )
        self._storage[feedback.id] = feedback
        return feedback

    def get_by_id(self, feedback_id: UUID, tenant_id: UUID) -> Optional[Feedback]:
        """
        Retrieve feedback by ID within tenant scope.

        Args:
            feedback_id: The feedback ID to look up
            tenant_id: Tenant scope for isolation

        Returns:
            Feedback if found and tenant matches, None otherwise
        """
        feedback = self._storage.get(feedback_id)
        if feedback and feedback.tenant_id == tenant_id:
            return feedback
        return None

    def get_by_recommendation(
        self, recommendation_id: UUID, tenant_id: UUID
    ) -> list[Feedback]:
        """
        Retrieve all feedback for a specific recommendation.

        Args:
            recommendation_id: The recommendation ID to filter by
            tenant_id: Tenant scope for isolation

        Returns:
            List of feedback entries for the recommendation
        """
        return [
            fb
            for fb in self._storage.values()
            if fb.recommendation_id == recommendation_id and fb.tenant_id == tenant_id
        ]

    def get_by_learner(self, learner_id: UUID, tenant_id: UUID) -> list[Feedback]:
        """
        Retrieve all feedback submitted by a specific learner.

        Args:
            learner_id: The learner ID to filter by
            tenant_id: Tenant scope for isolation

        Returns:
            List of feedback entries from the learner
        """
        return [
            fb
            for fb in self._storage.values()
            if fb.learner_id == learner_id and fb.tenant_id == tenant_id
        ]

    def list_by_tenant(
        self,
        tenant_id: UUID,
        feedback_type: Optional[FeedbackType] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Feedback]:
        """
        List all feedback within a tenant scope.

        Args:
            tenant_id: Tenant scope for isolation
            feedback_type: Optional filter by feedback type
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of feedback entries within tenant
        """
        results = [fb for fb in self._storage.values() if fb.tenant_id == tenant_id]

        if feedback_type:
            results = [fb for fb in results if fb.feedback_type == feedback_type]

        # Sort by created_at descending (newest first)
        results.sort(key=lambda fb: fb.created_at, reverse=True)

        return results[offset : offset + limit]

    def count_by_tenant(self, tenant_id: UUID) -> int:
        """
        Count all feedback entries for a tenant.

        Args:
            tenant_id: Tenant scope for isolation

        Returns:
            Count of feedback entries
        """
        return sum(1 for fb in self._storage.values() if fb.tenant_id == tenant_id)

    def delete(self, feedback_id: UUID, tenant_id: UUID) -> bool:
        """
        Delete feedback by ID within tenant scope.

        Args:
            feedback_id: The feedback ID to delete
            tenant_id: Tenant scope for isolation

        Returns:
            True if deleted, False if not found or tenant mismatch
        """
        feedback = self._storage.get(feedback_id)
        if feedback and feedback.tenant_id == tenant_id:
            del self._storage[feedback_id]
            return True
        return False

    def clear_tenant(self, tenant_id: UUID) -> int:
        """
        Clear all feedback for a tenant (for testing/admin use).

        Args:
            tenant_id: Tenant scope to clear

        Returns:
            Number of entries deleted
        """
        to_delete = [
            fid for fid, fb in self._storage.items() if fb.tenant_id == tenant_id
        ]
        for fid in to_delete:
            del self._storage[fid]
        return len(to_delete)
