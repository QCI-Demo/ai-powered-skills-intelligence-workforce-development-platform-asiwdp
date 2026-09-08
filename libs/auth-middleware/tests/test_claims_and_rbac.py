"""Unit tests for claim parsing, RBAC expansion, and JwtVerifier."""

from __future__ import annotations

import pytest

from asiwdp_auth.claims import AccessTokenClaims
from asiwdp_auth.errors import ClaimValidationError, TokenExpiredError, TokenInvalidError
from asiwdp_auth.jwt_verifier import JwtVerifier
from asiwdp_auth.rbac import RbacPolicy
from tests.conftest import make_token


class TestAccessTokenClaims:
    def test_parses_canonical_claims(self) -> None:
        claims = AccessTokenClaims.from_payload(
            {
                "sub": "u1",
                "tenant_id": "t1",
                "iat": 1,
                "exp": 2,
                "iss": "https://issuer/",
                "aud": "asiwdp-api",
                "roles": ["learner"],
                "scopes": ["skills:read"],
                "permissions": ["progress:write"],
            }
        )
        assert claims.subject == "u1"
        assert claims.tenant_id == "t1"
        assert claims.roles == ("learner",)
        assert claims.scopes == ("skills:read",)
        assert claims.permissions == ("progress:write",)

    def test_space_delimited_scope_string(self) -> None:
        claims = AccessTokenClaims.from_payload(
            {
                "sub": "u1",
                "tenant_id": "t1",
                "iat": 1,
                "exp": 2,
                "iss": "https://issuer/",
                "aud": ["asiwdp-api"],
                "scope": "skills:read progress:write",
            }
        )
        assert claims.scopes == ("skills:read", "progress:write")

    def test_missing_tenant_rejected_when_required(self) -> None:
        with pytest.raises(ClaimValidationError):
            AccessTokenClaims.from_payload(
                {
                    "sub": "u1",
                    "iat": 1,
                    "exp": 2,
                    "iss": "https://issuer/",
                    "aud": "asiwdp-api",
                },
                require_tenant=True,
            )


class TestRbacPolicy:
    def test_learner_permissions(self, rbac_policy: RbacPolicy) -> None:
        perms = rbac_policy.permissions_for_roles(["learner"])
        assert "skills:read" in perms
        assert "progress:write" in perms
        assert "skills:write" not in perms

    def test_platform_admin_wildcard(self, rbac_policy: RbacPolicy) -> None:
        perms = rbac_policy.permissions_for_roles(["platform_admin"])
        assert "*" in perms

    def test_expand_unions_scopes_and_roles(self, rbac_policy: RbacPolicy) -> None:
        effective = rbac_policy.expand_effective_permissions(
            roles=["learner"],
            scopes=["analytics:read"],
            permissions=["usage:read"],
        )
        assert "skills:read" in effective
        assert "analytics:read" in effective
        assert "usage:read" in effective


class TestJwtVerifier:
    def test_verify_builds_principal(self, auth_config, rbac_policy) -> None:
        verifier = JwtVerifier(auth_config, rbac_policy)
        token = make_token(roles=["skills_manager"])
        principal = verifier.verify(token)
        assert principal.subject.startswith("1111")
        assert principal.has_permission("skills:write")
        assert principal.has_role("skills_manager")

    def test_verify_expired(self, auth_config, rbac_policy) -> None:
        verifier = JwtVerifier(auth_config, rbac_policy)
        token = make_token(exp_offset=-30, iat_offset=-120)
        with pytest.raises(TokenExpiredError):
            verifier.verify(token)

    def test_verify_tampered(self, auth_config, rbac_policy) -> None:
        verifier = JwtVerifier(auth_config, rbac_policy)
        token = make_token()
        header, payload, sig = token.split(".")
        with pytest.raises(TokenInvalidError):
            verifier.verify(f"{header}.{payload}.{sig[:-3]}zzz")
