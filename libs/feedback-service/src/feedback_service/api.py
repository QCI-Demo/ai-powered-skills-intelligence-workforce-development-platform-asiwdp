"""
Feedback API endpoints.

Provides RESTful endpoints for learner feedback ingestion, protected by
OAuth2/JWT with tenant-scoped RBAC.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from feedback_service.models import FeedbackCreate, FeedbackResponse, FeedbackType
from feedback_service.repository import FeedbackRepository


class FeedbackAPI:
    """
    Feedback API handler with tenant-aware endpoints.

    Endpoints:
    - POST /feedback: Submit learner feedback on a recommendation
    - GET /feedback/{feedback_id}: Retrieve specific feedback
    - GET /feedback: List feedback (with filters)
    """

    def __init__(self, repository: Optional[FeedbackRepository] = None) -> None:
        """Initialize the API with a repository instance."""
        self.repository = repository or FeedbackRepository()

    async def create_feedback(self, request: Request) -> JSONResponse:
        """
        POST /feedback - Submit learner feedback.

        Requires: recommendations:read permission (learner role).

        Request body:
            - recommendation_id: UUID of the recommendation
            - feedback_type: "accept" or "reject"
            - rating: Optional 1-5 rating
            - comment: Optional text comment

        Returns:
            201: Created feedback with full details
            400: Validation error
            401: Missing/invalid JWT
            403: RBAC denial
        """
        # Extract tenant context from request state (set by auth middleware)
        tenant_id = getattr(request.state, "tenant_id", None)
        learner_id = getattr(request.state, "user_id", None)
        model_version = getattr(request.state, "model_version", None)

        if not tenant_id or not learner_id:
            return JSONResponse(
                {"error": "unauthorized", "message": "Missing tenant or user context"},
                status_code=401,
            )

        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                {"error": "bad_request", "message": "Invalid JSON body"},
                status_code=400,
            )

        # Validate required fields
        errors = []

        if "recommendation_id" not in body:
            errors.append("recommendation_id is required")
        else:
            try:
                body["recommendation_id"] = UUID(str(body["recommendation_id"]))
            except (ValueError, TypeError):
                errors.append("recommendation_id must be a valid UUID")

        if "feedback_type" not in body:
            errors.append("feedback_type is required")
        elif body["feedback_type"] not in ("accept", "reject"):
            errors.append("feedback_type must be 'accept' or 'reject'")

        if "rating" in body and body["rating"] is not None:
            try:
                rating = int(body["rating"])
                if rating < 1 or rating > 5:
                    errors.append("rating must be between 1 and 5")
            except (ValueError, TypeError):
                errors.append("rating must be an integer")

        if "comment" in body and body["comment"] is not None:
            if not isinstance(body["comment"], str):
                errors.append("comment must be a string")
            elif len(body["comment"]) > 2000:
                errors.append("comment must be 2000 characters or less")

        if errors:
            return JSONResponse(
                {"error": "validation_error", "message": "; ".join(errors)},
                status_code=400,
            )

        try:
            feedback_data = FeedbackCreate(
                recommendation_id=body["recommendation_id"],
                feedback_type=FeedbackType(body["feedback_type"]),
                rating=body.get("rating"),
                comment=body.get("comment"),
            )
        except Exception as e:
            return JSONResponse(
                {"error": "validation_error", "message": str(e)},
                status_code=400,
            )

        feedback = self.repository.create(
            tenant_id=UUID(str(tenant_id)),
            learner_id=UUID(str(learner_id)),
            feedback_data=feedback_data,
            model_version=model_version,
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

        return JSONResponse(
            response.model_dump(mode="json"),
            status_code=201,
            headers={"X-Model-Version": feedback.model_version or "unknown"},
        )

    async def get_feedback(self, request: Request) -> JSONResponse:
        """
        GET /feedback/{feedback_id} - Retrieve specific feedback.

        Requires: recommendations:read permission.

        Returns:
            200: Feedback details
            404: Feedback not found
            401: Missing/invalid JWT
            403: RBAC denial
        """
        tenant_id = getattr(request.state, "tenant_id", None)
        if not tenant_id:
            return JSONResponse(
                {"error": "unauthorized", "message": "Missing tenant context"},
                status_code=401,
            )

        feedback_id_str = request.path_params.get("feedback_id")
        try:
            feedback_id = UUID(feedback_id_str)
        except (ValueError, TypeError):
            return JSONResponse(
                {"error": "bad_request", "message": "Invalid feedback_id format"},
                status_code=400,
            )

        feedback = self.repository.get_by_id(feedback_id, UUID(str(tenant_id)))
        if not feedback:
            return JSONResponse(
                {"error": "not_found", "message": "Feedback not found"},
                status_code=404,
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

        return JSONResponse(response.model_dump(mode="json"))

    async def list_feedback(self, request: Request) -> JSONResponse:
        """
        GET /feedback - List feedback with optional filters.

        Query params:
            - recommendation_id: Filter by recommendation
            - learner_id: Filter by learner
            - feedback_type: Filter by type (accept/reject)
            - limit: Max results (default 100)
            - offset: Pagination offset

        Requires: recommendations:read permission.

        Returns:
            200: List of feedback entries with pagination metadata
            401: Missing/invalid JWT
            403: RBAC denial
        """
        tenant_id = getattr(request.state, "tenant_id", None)
        if not tenant_id:
            return JSONResponse(
                {"error": "unauthorized", "message": "Missing tenant context"},
                status_code=401,
            )

        tenant_uuid = UUID(str(tenant_id))

        # Parse query parameters
        params = request.query_params
        recommendation_id = params.get("recommendation_id")
        learner_id = params.get("learner_id")
        feedback_type_str = params.get("feedback_type")

        try:
            limit = int(params.get("limit", 100))
            limit = min(max(1, limit), 1000)  # Clamp between 1 and 1000
        except ValueError:
            limit = 100

        try:
            offset = int(params.get("offset", 0))
            offset = max(0, offset)
        except ValueError:
            offset = 0

        # Apply filters
        if recommendation_id:
            try:
                rec_uuid = UUID(recommendation_id)
                results = self.repository.get_by_recommendation(rec_uuid, tenant_uuid)
            except ValueError:
                return JSONResponse(
                    {
                        "error": "bad_request",
                        "message": "Invalid recommendation_id format",
                    },
                    status_code=400,
                )
        elif learner_id:
            try:
                learner_uuid = UUID(learner_id)
                results = self.repository.get_by_learner(learner_uuid, tenant_uuid)
            except ValueError:
                return JSONResponse(
                    {"error": "bad_request", "message": "Invalid learner_id format"},
                    status_code=400,
                )
        else:
            feedback_type = None
            if feedback_type_str:
                try:
                    feedback_type = FeedbackType(feedback_type_str)
                except ValueError:
                    return JSONResponse(
                        {
                            "error": "bad_request",
                            "message": "feedback_type must be 'accept' or 'reject'",
                        },
                        status_code=400,
                    )
            results = self.repository.list_by_tenant(
                tenant_uuid, feedback_type=feedback_type, limit=limit, offset=offset
            )

        total = self.repository.count_by_tenant(tenant_uuid)

        items = [
            FeedbackResponse(
                id=fb.id,
                tenant_id=fb.tenant_id,
                learner_id=fb.learner_id,
                recommendation_id=fb.recommendation_id,
                feedback_type=fb.feedback_type,
                rating=fb.rating,
                comment=fb.comment,
                created_at=fb.created_at,
                model_version=fb.model_version,
            ).model_dump(mode="json")
            for fb in results
        ]

        return JSONResponse(
            {
                "items": items,
                "total": total,
                "limit": limit,
                "offset": offset,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    async def health(self, request: Request) -> JSONResponse:
        """Health check endpoint."""
        return JSONResponse({"status": "healthy", "service": "feedback-service"})


def create_feedback_router(repository: Optional[FeedbackRepository] = None) -> list:
    """
    Create Starlette routes for the feedback API.

    Args:
        repository: Optional FeedbackRepository instance

    Returns:
        List of Starlette Route objects
    """
    api = FeedbackAPI(repository)

    return [
        Route("/health", api.health, methods=["GET"]),
        Route("/feedback", api.create_feedback, methods=["POST"]),
        Route("/feedback", api.list_feedback, methods=["GET"]),
        Route("/feedback/{feedback_id}", api.get_feedback, methods=["GET"]),
    ]


def create_app(repository: Optional[FeedbackRepository] = None) -> Starlette:
    """
    Create a Starlette application with feedback routes.

    Args:
        repository: Optional FeedbackRepository instance

    Returns:
        Configured Starlette application
    """
    routes = create_feedback_router(repository)
    return Starlette(routes=routes)
