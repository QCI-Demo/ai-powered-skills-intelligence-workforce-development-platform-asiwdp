"""JWT helpers for tests (no secrets logged)."""

from __future__ import annotations

import time

import jwt

TEST_ISSUER = "https://auth.asiwdp.example/"
TEST_AUDIENCE = "asiwdp-api"
TEST_SECRET = "test-tenant-provisioning-secret-not-for-prod"


def make_token(
    *,
    sub: str = "11111111-1111-1111-1111-111111111111",
    tenant_id: str = "22222222-2222-2222-2222-222222222222",
    roles: list[str] | None = None,
    scopes: list[str] | None = None,
    permissions: list[str] | None = None,
    exp_offset: int = 3600,
    issuer: str = TEST_ISSUER,
    audience: str = TEST_AUDIENCE,
    secret: str = TEST_SECRET,
) -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "tenant_id": tenant_id,
        "iat": now,
        "exp": now + exp_offset,
        "iss": issuer,
        "aud": audience,
        "roles": roles or ["platform_admin"],
        "scopes": scopes or [],
    }
    if permissions is not None:
        payload["permissions"] = permissions
    return jwt.encode(payload, secret, algorithm="HS256")
