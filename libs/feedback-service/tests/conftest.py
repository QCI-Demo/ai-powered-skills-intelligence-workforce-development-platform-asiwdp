"""Test configuration and fixtures for feedback service tests."""

import pytest
from uuid import uuid4

from starlette.testclient import TestClient

from feedback_service.repository import FeedbackRepository
from feedback_service.api import create_app


@pytest.fixture
def repository():
    """Provide a fresh FeedbackRepository for each test."""
    return FeedbackRepository()


@pytest.fixture
def tenant_id():
    """Provide a test tenant ID."""
    return uuid4()


@pytest.fixture
def learner_id():
    """Provide a test learner ID."""
    return uuid4()


@pytest.fixture
def recommendation_id():
    """Provide a test recommendation ID."""
    return uuid4()


class AuthenticatedTestClient(TestClient):
    """Test client that simulates authenticated requests."""

    def __init__(self, app, tenant_id, user_id, model_version=None):
        super().__init__(app)
        self._tenant_id = tenant_id
        self._user_id = user_id
        self._model_version = model_version

    def request(self, method, url, **kwargs):
        """Override request to inject auth context."""
        # Store context for the middleware simulation
        self._current_request_context = {
            "tenant_id": self._tenant_id,
            "user_id": self._user_id,
            "model_version": self._model_version,
        }
        return super().request(method, url, **kwargs)


@pytest.fixture
def app(repository):
    """Create a test application."""
    app = create_app(repository)

    # Add middleware to simulate authentication
    from starlette.middleware import Middleware
    from starlette.middleware.base import BaseHTTPMiddleware

    class MockAuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            # Get auth context from test headers
            tenant_id = request.headers.get("X-Tenant-ID")
            user_id = request.headers.get("X-User-ID")
            model_version = request.headers.get("X-Model-Version")

            if tenant_id:
                request.state.tenant_id = tenant_id
            if user_id:
                request.state.user_id = user_id
            if model_version:
                request.state.model_version = model_version

            return await call_next(request)

    app.add_middleware(MockAuthMiddleware)
    return app


@pytest.fixture
def client(app, tenant_id, learner_id):
    """Create an authenticated test client."""
    with TestClient(app) as client:
        # Set default auth headers
        client.headers.update({
            "X-Tenant-ID": str(tenant_id),
            "X-User-ID": str(learner_id),
            "X-Model-Version": "v1.0.0-test",
        })
        yield client


@pytest.fixture
def unauthenticated_client(app):
    """Create an unauthenticated test client."""
    with TestClient(app) as client:
        yield client
