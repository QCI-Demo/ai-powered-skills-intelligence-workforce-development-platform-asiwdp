"""
PyTest configuration for ASIWDP Integration Tests.

Provides shared fixtures, markers, and configuration for tenant isolation
and API integration testing.
"""

import os
import pytest


def pytest_addoption(parser):
    """Add custom command line options for integration tests."""
    parser.addoption(
        "--skills-api-url",
        action="store",
        default=os.getenv("SKILLS_API_BASE_URL", "http://localhost:8080/api/v1"),
        help="Base URL for the Skills API service",
    )
    parser.addoption(
        "--audit-api-url",
        action="store",
        default=os.getenv("AUDIT_LOG_API_URL", "http://localhost:8081/api/v1/audit"),
        help="Base URL for the Audit Log API service",
    )
    parser.addoption(
        "--tenant-a-id",
        action="store",
        default=os.getenv("TENANT_A_ID"),
        help="Tenant A ID for isolation tests",
    )
    parser.addoption(
        "--tenant-a-token",
        action="store",
        default=os.getenv("TENANT_A_TOKEN"),
        help="OAuth2 token for Tenant A",
    )
    parser.addoption(
        "--tenant-b-id",
        action="store",
        default=os.getenv("TENANT_B_ID"),
        help="Tenant B ID for isolation tests",
    )
    parser.addoption(
        "--tenant-b-token",
        action="store",
        default=os.getenv("TENANT_B_TOKEN"),
        help="OAuth2 token for Tenant B",
    )


@pytest.fixture(scope="session")
def api_base_url(request) -> str:
    """Return the Skills API base URL."""
    return request.config.getoption("--skills-api-url")


@pytest.fixture(scope="session")
def audit_api_url(request) -> str:
    """Return the Audit Log API base URL."""
    return request.config.getoption("--audit-api-url")


def pytest_collection_modifyitems(config, items):
    """Add markers to tests based on their location."""
    for item in items:
        if "tenant_isolation" in item.nodeid:
            item.add_marker(pytest.mark.tenant_isolation)
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "tenant_isolation: marks tests as tenant isolation tests",
    )
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests requiring live services",
    )
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow running",
    )
