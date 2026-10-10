"""Integration tests for Feedback API endpoints."""

import pytest
from uuid import uuid4


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "feedback-service"


class TestCreateFeedbackEndpoint:
    """Tests for POST /feedback endpoint."""

    def test_create_accept_feedback_success(self, client, recommendation_id):
        response = client.post(
            "/feedback",
            json={
                "recommendation_id": str(recommendation_id),
                "feedback_type": "accept",
                "rating": 5,
                "comment": "Great recommendation!",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["recommendation_id"] == str(recommendation_id)
        assert data["feedback_type"] == "accept"
        assert data["rating"] == 5
        assert data["comment"] == "Great recommendation!"
        assert "id" in data
        assert "tenant_id" in data
        assert "learner_id" in data
        assert "created_at" in data

    def test_create_reject_feedback_success(self, client, recommendation_id):
        response = client.post(
            "/feedback",
            json={
                "recommendation_id": str(recommendation_id),
                "feedback_type": "reject",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["feedback_type"] == "reject"
        assert data["rating"] is None

    def test_create_feedback_minimal_payload(self, client, recommendation_id):
        """Test with only required fields."""
        response = client.post(
            "/feedback",
            json={
                "recommendation_id": str(recommendation_id),
                "feedback_type": "accept",
            },
        )
        assert response.status_code == 201

    def test_create_feedback_includes_model_version_header(
        self, client, recommendation_id
    ):
        response = client.post(
            "/feedback",
            json={
                "recommendation_id": str(recommendation_id),
                "feedback_type": "accept",
            },
        )
        assert response.status_code == 201
        assert "X-Model-Version" in response.headers

    def test_create_feedback_missing_recommendation_id(self, client):
        response = client.post(
            "/feedback",
            json={
                "feedback_type": "accept",
            },
        )
        assert response.status_code == 400
        assert "recommendation_id" in response.json()["message"]

    def test_create_feedback_missing_feedback_type(self, client, recommendation_id):
        response = client.post(
            "/feedback",
            json={
                "recommendation_id": str(recommendation_id),
            },
        )
        assert response.status_code == 400
        assert "feedback_type" in response.json()["message"]

    def test_create_feedback_invalid_feedback_type(self, client, recommendation_id):
        response = client.post(
            "/feedback",
            json={
                "recommendation_id": str(recommendation_id),
                "feedback_type": "invalid",
            },
        )
        assert response.status_code == 400
        assert "feedback_type" in response.json()["message"]

    def test_create_feedback_invalid_recommendation_id(self, client):
        response = client.post(
            "/feedback",
            json={
                "recommendation_id": "not-a-uuid",
                "feedback_type": "accept",
            },
        )
        assert response.status_code == 400
        assert "recommendation_id" in response.json()["message"]

    def test_create_feedback_rating_below_minimum(self, client, recommendation_id):
        response = client.post(
            "/feedback",
            json={
                "recommendation_id": str(recommendation_id),
                "feedback_type": "accept",
                "rating": 0,
            },
        )
        assert response.status_code == 400
        assert "rating" in response.json()["message"]

    def test_create_feedback_rating_above_maximum(self, client, recommendation_id):
        response = client.post(
            "/feedback",
            json={
                "recommendation_id": str(recommendation_id),
                "feedback_type": "accept",
                "rating": 6,
            },
        )
        assert response.status_code == 400
        assert "rating" in response.json()["message"]

    def test_create_feedback_comment_too_long(self, client, recommendation_id):
        response = client.post(
            "/feedback",
            json={
                "recommendation_id": str(recommendation_id),
                "feedback_type": "accept",
                "comment": "x" * 2001,
            },
        )
        assert response.status_code == 400
        assert "comment" in response.json()["message"]

    def test_create_feedback_invalid_json_body(self, client):
        response = client.post(
            "/feedback",
            content="not json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400
        assert "Invalid JSON" in response.json()["message"]

    def test_create_feedback_unauthenticated(
        self, unauthenticated_client, recommendation_id
    ):
        response = unauthenticated_client.post(
            "/feedback",
            json={
                "recommendation_id": str(recommendation_id),
                "feedback_type": "accept",
            },
        )
        assert response.status_code == 401


class TestGetFeedbackEndpoint:
    """Tests for GET /feedback/{feedback_id} endpoint."""

    def test_get_feedback_success(self, client, recommendation_id):
        # First create feedback
        create_response = client.post(
            "/feedback",
            json={
                "recommendation_id": str(recommendation_id),
                "feedback_type": "accept",
                "rating": 4,
            },
        )
        assert create_response.status_code == 201
        feedback_id = create_response.json()["id"]

        # Then retrieve it
        response = client.get(f"/feedback/{feedback_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == feedback_id
        assert data["rating"] == 4

    def test_get_feedback_not_found(self, client):
        response = client.get(f"/feedback/{uuid4()}")
        assert response.status_code == 404

    def test_get_feedback_invalid_id_format(self, client):
        response = client.get("/feedback/not-a-uuid")
        assert response.status_code == 400
        assert "feedback_id" in response.json()["message"]

    def test_get_feedback_unauthenticated(self, unauthenticated_client):
        response = unauthenticated_client.get(f"/feedback/{uuid4()}")
        assert response.status_code == 401


class TestListFeedbackEndpoint:
    """Tests for GET /feedback endpoint."""

    def test_list_feedback_empty(self, client):
        response = client.get("/feedback")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_feedback_with_entries(self, client, recommendation_id):
        # Create some feedback
        for i in range(3):
            client.post(
                "/feedback",
                json={
                    "recommendation_id": str(recommendation_id),
                    "feedback_type": "accept",
                    "rating": i + 1,
                },
            )

        response = client.get("/feedback")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["total"] == 3

    def test_list_feedback_filter_by_recommendation(self, client):
        rec1 = uuid4()
        rec2 = uuid4()

        for _ in range(2):
            client.post(
                "/feedback",
                json={
                    "recommendation_id": str(rec1),
                    "feedback_type": "accept",
                },
            )

        client.post(
            "/feedback",
            json={
                "recommendation_id": str(rec2),
                "feedback_type": "reject",
            },
        )

        response = client.get(f"/feedback?recommendation_id={rec1}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2

    def test_list_feedback_filter_by_type(self, client):
        rec = uuid4()

        for i in range(5):
            client.post(
                "/feedback",
                json={
                    "recommendation_id": str(rec),
                    "feedback_type": "accept" if i % 2 == 0 else "reject",
                },
            )

        response = client.get("/feedback?feedback_type=accept")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert all(item["feedback_type"] == "accept" for item in data["items"])

    def test_list_feedback_pagination(self, client):
        rec = uuid4()
        for _ in range(10):
            client.post(
                "/feedback",
                json={
                    "recommendation_id": str(rec),
                    "feedback_type": "accept",
                },
            )

        response = client.get("/feedback?limit=3&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["limit"] == 3
        assert data["offset"] == 0

    def test_list_feedback_invalid_recommendation_id(self, client):
        response = client.get("/feedback?recommendation_id=not-a-uuid")
        assert response.status_code == 400

    def test_list_feedback_invalid_feedback_type(self, client):
        response = client.get("/feedback?feedback_type=invalid")
        assert response.status_code == 400

    def test_list_feedback_unauthenticated(self, unauthenticated_client):
        response = unauthenticated_client.get("/feedback")
        assert response.status_code == 401

    def test_list_feedback_includes_timestamp(self, client, recommendation_id):
        client.post(
            "/feedback",
            json={
                "recommendation_id": str(recommendation_id),
                "feedback_type": "accept",
            },
        )

        response = client.get("/feedback")
        assert response.status_code == 200
        assert "timestamp" in response.json()


class TestTenantIsolation:
    """Tests for tenant isolation in feedback operations."""

    def test_feedback_isolated_by_tenant(self, app, recommendation_id):
        """Verify feedback from one tenant is not visible to another."""
        from starlette.testclient import TestClient

        tenant1 = uuid4()
        tenant2 = uuid4()
        user = uuid4()

        with TestClient(app) as client1:
            client1.headers.update({
                "X-Tenant-ID": str(tenant1),
                "X-User-ID": str(user),
            })
            # Create feedback in tenant 1
            response = client1.post(
                "/feedback",
                json={
                    "recommendation_id": str(recommendation_id),
                    "feedback_type": "accept",
                },
            )
            assert response.status_code == 201
            feedback_id = response.json()["id"]

        with TestClient(app) as client2:
            client2.headers.update({
                "X-Tenant-ID": str(tenant2),
                "X-User-ID": str(user),
            })
            # Try to access feedback from tenant 2
            response = client2.get(f"/feedback/{feedback_id}")
            assert response.status_code == 404

            # List should be empty for tenant 2
            response = client2.get("/feedback")
            assert response.status_code == 200
            assert len(response.json()["items"]) == 0
