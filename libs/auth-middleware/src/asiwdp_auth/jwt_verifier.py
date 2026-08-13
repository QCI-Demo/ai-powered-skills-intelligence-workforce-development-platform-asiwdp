"""JWT verification and principal resolution."""

from __future__ import annotations

from typing import Any

import jwt
from jwt.exceptions import (
    ExpiredSignatureError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidSignatureError,
    InvalidTokenError,
    PyJWTError,
)

from asiwdp_auth.claims import AccessTokenClaims
from asiwdp_auth.config import AuthConfig
from asiwdp_auth.context import Principal
from asiwdp_auth.errors import (
    ClaimValidationError,
    TokenExpiredError,
    TokenInvalidError,
)
from asiwdp_auth.rbac import RbacPolicy


class JwtVerifier:
    """Verifies JWT access tokens and builds Principals."""

    def __init__(self, config: AuthConfig, policy: RbacPolicy) -> None:
        self._config = config
        self._policy = policy

    @property
    def config(self) -> AuthConfig:
        return self._config

    @property
    def policy(self) -> RbacPolicy:
        return self._policy

    def decode_payload(self, token: str) -> dict[str, Any]:
        """Verify signature and standard claims; return raw payload."""
        try:
            payload = jwt.decode(
                token,
                key=self._config.verification_key,
                algorithms=[self._config.algorithm],
                audience=self._config.audiences(),
                issuer=self._config.issuer,
                leeway=self._config.leeway_seconds,
                options={
                    "require": ["exp", "iat", "iss", "aud", "sub"],
                },
            )
        except ExpiredSignatureError as exc:
            raise TokenExpiredError("Access token has expired") from exc
        except InvalidSignatureError as exc:
            raise TokenInvalidError("Access token signature is invalid") from exc
        except (InvalidAudienceError, InvalidIssuerError) as exc:
            raise TokenInvalidError(f"Access token audience/issuer invalid: {exc}") from exc
        except InvalidTokenError as exc:
            raise TokenInvalidError(f"Access token is invalid: {exc}") from exc
        except PyJWTError as exc:
            raise TokenInvalidError(f"Access token verification failed: {exc}") from exc

        if not isinstance(payload, dict):
            raise TokenInvalidError("Access token payload must be an object")
        return payload

    def verify(self, token: str) -> Principal:
        """Verify token and resolve an authenticated Principal."""
        payload = self.decode_payload(token)
        try:
            claims = AccessTokenClaims.from_payload(
                payload, require_tenant=self._config.require_tenant
            )
        except ClaimValidationError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            raise ClaimValidationError(f"Claim validation failed: {exc}") from exc

        effective = self._policy.expand_effective_permissions(
            roles=claims.roles,
            scopes=claims.scopes,
            permissions=claims.permissions,
        )
        return Principal(
            subject=claims.subject,
            tenant_id=claims.tenant_id,
            roles=claims.roles,
            scopes=claims.scopes,
            effective_permissions=effective,
            actor_type=claims.actor_type,
            session_id=claims.session_id,
            org_id=claims.org_id,
            claims=claims,
        )
