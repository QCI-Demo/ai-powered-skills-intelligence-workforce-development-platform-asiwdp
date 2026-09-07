"""Shared fixtures for skills-framework service tests."""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from asiwdp_skills_framework.app import create_app

DEMO_TENANT = UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture()
def app():
    return create_app(enable_auth=False)


@pytest.fixture()
def client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture()
def tenant_headers() -> dict[str, str]:
    return {
        "X-Tenant-Id": str(DEMO_TENANT),
        "X-Taxonomy-Version": "1",
    }
