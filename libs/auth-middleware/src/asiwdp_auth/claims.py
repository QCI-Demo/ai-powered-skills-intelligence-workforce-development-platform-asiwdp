"""JWT access-token claim models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from asiwdp_auth.errors import ClaimValidationError


def _as_str_list(value: Any, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        # Space-delimited OAuth2 scope string
        return tuple(part for part in value.split() if part)
    if isinstance(value, (list, tuple, set)):
        result: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ClaimValidationError(
                    f"Claim '{field_name}' must be a list of non-empty strings"
                )
            result.append(item.strip())
        return tuple(result)
    raise ClaimValidationError(f"Claim '{field_name}' has invalid type")


def _first_present(payload: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return None


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    """Canonical ASIWDP access-token claims after normalization."""

    subject: str
    tenant_id: str | None
    roles: tuple[str, ...]
    scopes: tuple[str, ...]
    permissions: tuple[str, ...]
    issuer: str
    audience: tuple[str, ...]
    issued_at: int
    expires_at: int
    session_id: str | None = None
    org_id: str | None = None
    actor_type: str = "user"
    token_id: str | None = None
    authorized_party: str | None = None
    raw: Mapping[str, Any] | None = None

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        require_tenant: bool = True,
    ) -> AccessTokenClaims:
        """Parse and validate claims from a verified JWT payload."""
        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject.strip():
            raise ClaimValidationError("Missing or invalid 'sub' claim")

        tenant_id = _first_present(payload, "tenant_id", "tenantId")
        if tenant_id is not None and (
            not isinstance(tenant_id, str) or not tenant_id.strip()
        ):
            raise ClaimValidationError("Invalid 'tenant_id' claim")
        if require_tenant and not tenant_id:
            raise ClaimValidationError("Missing required 'tenant_id' claim")

        issuer = payload.get("iss")
        if not isinstance(issuer, str) or not issuer.strip():
            raise ClaimValidationError("Missing or invalid 'iss' claim")

        aud = payload.get("aud")
        if isinstance(aud, str):
            audience = (aud,)
        elif isinstance(aud, (list, tuple)):
            if not all(isinstance(a, str) and a for a in aud):
                raise ClaimValidationError("Invalid 'aud' claim")
            audience = tuple(aud)
        else:
            raise ClaimValidationError("Missing or invalid 'aud' claim")

        iat = payload.get("iat")
        exp = payload.get("exp")
        if not isinstance(iat, int):
            raise ClaimValidationError("Missing or invalid 'iat' claim")
        if not isinstance(exp, int):
            raise ClaimValidationError("Missing or invalid 'exp' claim")

        roles = _as_str_list(_first_present(payload, "roles"), "roles")
        scopes = _as_str_list(_first_present(payload, "scopes", "scope"), "scopes")
        permissions = _as_str_list(
            _first_present(payload, "permissions"), "permissions"
        )

        session_id = _first_present(payload, "session_id", "sessionId")
        if session_id is not None and not isinstance(session_id, str):
            raise ClaimValidationError("Invalid 'session_id' claim")

        org_id = _first_present(payload, "org_id", "orgId")
        if org_id is not None and not isinstance(org_id, str):
            raise ClaimValidationError("Invalid 'org_id' claim")

        actor_type = _first_present(payload, "actor_type", "actorType") or "user"
        if not isinstance(actor_type, str):
            raise ClaimValidationError("Invalid 'actor_type' claim")

        token_id = payload.get("jti")
        if token_id is not None and not isinstance(token_id, str):
            raise ClaimValidationError("Invalid 'jti' claim")

        azp = payload.get("azp")
        if azp is not None and not isinstance(azp, str):
            raise ClaimValidationError("Invalid 'azp' claim")

        return cls(
            subject=subject.strip(),
            tenant_id=tenant_id.strip() if isinstance(tenant_id, str) else None,
            roles=roles,
            scopes=scopes,
            permissions=permissions,
            issuer=issuer.strip(),
            audience=audience,
            issued_at=iat,
            expires_at=exp,
            session_id=session_id,
            org_id=org_id,
            actor_type=actor_type,
            token_id=token_id,
            authorized_party=azp,
            raw=dict(payload),
        )

    def to_dict(self) -> dict[str, Any]:
        """Safe serialization for logs / audit (no secrets)."""
        return {
            "sub": self.subject,
            "tenant_id": self.tenant_id,
            "roles": list(self.roles),
            "scopes": list(self.scopes),
            "permissions": list(self.permissions),
            "iss": self.issuer,
            "aud": list(self.audience),
            "iat": self.issued_at,
            "exp": self.expires_at,
            "session_id": self.session_id,
            "org_id": self.org_id,
            "actor_type": self.actor_type,
            "jti": self.token_id,
        }
