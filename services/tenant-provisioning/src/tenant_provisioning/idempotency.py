"""Idempotency key handling for safe request replay."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from tenant_provisioning.config import get_settings
from tenant_provisioning.entities import IdempotencyKey


class IdempotencyService:
    """Service for managing idempotency keys."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()

    @staticmethod
    def compute_request_hash(payload: dict[str, Any]) -> str:
        """Compute SHA-256 hash of request payload."""
        serialized = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()

    async def get_cached_response(
        self,
        idempotency_key: str,
        request_hash: str,
    ) -> tuple[dict[str, Any], int] | None:
        """Retrieve cached response for idempotency key if valid.

        Returns:
            Tuple of (response_body, status_code) if found and hash matches.
            None if not found, expired, or hash mismatch.
        """
        stmt = select(IdempotencyKey).where(
            IdempotencyKey.idempotency_key == idempotency_key
        )
        result = await self._session.execute(stmt)
        record = result.scalar_one_or_none()

        if record is None:
            return None

        now = datetime.now(timezone.utc)
        if record.expires_at < now:
            # Expired - delete and return None
            await self._session.delete(record)
            await self._session.flush()
            return None

        if record.request_hash != request_hash:
            # Different request with same key - conflict
            raise IdempotencyConflictError(
                "Idempotency key reused with different request payload"
            )

        return record.response_body, record.status_code

    async def store_response(
        self,
        idempotency_key: str,
        request_hash: str,
        response_body: dict[str, Any],
        status_code: int,
        tenant_id: UUID | None = None,
    ) -> None:
        """Store response for idempotency key."""
        ttl_hours = self._settings.idempotency_ttl_hours
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)

        record = IdempotencyKey(
            idempotency_key=idempotency_key,
            tenant_id=tenant_id,
            request_hash=request_hash,
            response_body=response_body,
            status_code=status_code,
            expires_at=expires_at,
        )
        self._session.add(record)
        await self._session.flush()

    async def cleanup_expired(self) -> int:
        """Delete expired idempotency keys. Returns count deleted."""
        now = datetime.now(timezone.utc)
        stmt = delete(IdempotencyKey).where(IdempotencyKey.expires_at < now)
        result = await self._session.execute(stmt)
        return result.rowcount


class IdempotencyConflictError(Exception):
    """Raised when idempotency key is reused with different payload."""

    pass
