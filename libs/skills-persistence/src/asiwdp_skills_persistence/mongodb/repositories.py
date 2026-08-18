"""CRUD data-access functions for skill_meta and role_meta collections."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, MutableMapping, Optional
from uuid import UUID

from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.results import DeleteResult, UpdateResult

from asiwdp_skills_persistence.mongodb.collections import (
    ROLE_META_COLLECTION,
    SKILL_META_COLLECTION,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_uuid_str(value: str | UUID) -> str:
    if isinstance(value, UUID):
        return str(value)
    return str(UUID(str(value)))


def _require_positive_version(version: int) -> int:
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise ValueError("version must be an int >= 1")
    return version


class SkillMetaRepository:
    """Tenant-scoped CRUD for the ``skill_meta`` collection."""

    def __init__(self, db: Database) -> None:
        self._collection = db[SKILL_META_COLLECTION]

    def create(
        self,
        *,
        tenant_id: str | UUID,
        skill_id: str | UUID,
        version: int,
        metadata: Optional[Mapping[str, Any]] = None,
        tags: Optional[list[str]] = None,
        audit_entries: Optional[list[Mapping[str, Any]]] = None,
    ) -> dict[str, Any]:
        """Insert a new skill metadata document."""
        now = _utcnow()
        doc: dict[str, Any] = {
            "tenant_id": _as_uuid_str(tenant_id),
            "skill_id": _as_uuid_str(skill_id),
            "version": _require_positive_version(version),
            "metadata": dict(metadata or {}),
            "tags": list(tags or []),
            "audit_entries": list(audit_entries or []),
            "created_at": now,
            "updated_at": now,
        }
        result = self._collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    def get(
        self,
        *,
        tenant_id: str | UUID,
        skill_id: str | UUID,
        version: int,
    ) -> Optional[dict[str, Any]]:
        """Fetch one skill meta document by tenant/skill/version."""
        return self._collection.find_one(
            {
                "tenant_id": _as_uuid_str(tenant_id),
                "skill_id": _as_uuid_str(skill_id),
                "version": _require_positive_version(version),
            }
        )

    def list_for_tenant(
        self,
        *,
        tenant_id: str | UUID,
        version: Optional[int] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List skill meta documents for a tenant (optionally filtered by version)."""
        query: dict[str, Any] = {"tenant_id": _as_uuid_str(tenant_id)}
        if version is not None:
            query["version"] = _require_positive_version(version)
        cursor = self._collection.find(query).limit(max(1, min(limit, 1000)))
        return list(cursor)

    def update_metadata(
        self,
        *,
        tenant_id: str | UUID,
        skill_id: str | UUID,
        version: int,
        metadata: Mapping[str, Any],
        tags: Optional[list[str]] = None,
    ) -> Optional[dict[str, Any]]:
        """Replace metadata (and optional tags) on an existing document."""
        update: MutableMapping[str, Any] = {
            "metadata": dict(metadata),
            "updated_at": _utcnow(),
        }
        if tags is not None:
            update["tags"] = list(tags)
        return self._collection.find_one_and_update(
            {
                "tenant_id": _as_uuid_str(tenant_id),
                "skill_id": _as_uuid_str(skill_id),
                "version": _require_positive_version(version),
            },
            {"$set": update},
            return_document=ReturnDocument.AFTER,
        )

    def append_audit_entry(
        self,
        *,
        tenant_id: str | UUID,
        skill_id: str | UUID,
        version: int,
        action: str,
        actor_id: Optional[str | UUID] = None,
        detail: Optional[Mapping[str, Any]] = None,
    ) -> UpdateResult:
        """Append a flexible audit blob to the skill meta document."""
        entry = {
            "action": action,
            "at": _utcnow(),
            "actor_id": _as_uuid_str(actor_id) if actor_id is not None else None,
            "detail": dict(detail or {}),
        }
        return self._collection.update_one(
            {
                "tenant_id": _as_uuid_str(tenant_id),
                "skill_id": _as_uuid_str(skill_id),
                "version": _require_positive_version(version),
            },
            {
                "$push": {"audit_entries": entry},
                "$set": {"updated_at": _utcnow()},
            },
        )

    def delete(
        self,
        *,
        tenant_id: str | UUID,
        skill_id: str | UUID,
        version: int,
    ) -> DeleteResult:
        """Delete a skill meta document (tenant-scoped)."""
        return self._collection.delete_one(
            {
                "tenant_id": _as_uuid_str(tenant_id),
                "skill_id": _as_uuid_str(skill_id),
                "version": _require_positive_version(version),
            }
        )


class RoleMetaRepository:
    """Tenant-scoped CRUD for the ``role_meta`` collection."""

    def __init__(self, db: Database) -> None:
        self._collection = db[ROLE_META_COLLECTION]

    def create(
        self,
        *,
        tenant_id: str | UUID,
        role_id: str | UUID,
        version: int,
        metadata: Optional[Mapping[str, Any]] = None,
        tags: Optional[list[str]] = None,
        audit_entries: Optional[list[Mapping[str, Any]]] = None,
    ) -> dict[str, Any]:
        """Insert a new role metadata document."""
        now = _utcnow()
        doc: dict[str, Any] = {
            "tenant_id": _as_uuid_str(tenant_id),
            "role_id": _as_uuid_str(role_id),
            "version": _require_positive_version(version),
            "metadata": dict(metadata or {}),
            "tags": list(tags or []),
            "audit_entries": list(audit_entries or []),
            "created_at": now,
            "updated_at": now,
        }
        result = self._collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    def get(
        self,
        *,
        tenant_id: str | UUID,
        role_id: str | UUID,
        version: int,
    ) -> Optional[dict[str, Any]]:
        """Fetch one role meta document by tenant/role/version."""
        return self._collection.find_one(
            {
                "tenant_id": _as_uuid_str(tenant_id),
                "role_id": _as_uuid_str(role_id),
                "version": _require_positive_version(version),
            }
        )

    def list_for_tenant(
        self,
        *,
        tenant_id: str | UUID,
        version: Optional[int] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List role meta documents for a tenant (optionally filtered by version)."""
        query: dict[str, Any] = {"tenant_id": _as_uuid_str(tenant_id)}
        if version is not None:
            query["version"] = _require_positive_version(version)
        cursor = self._collection.find(query).limit(max(1, min(limit, 1000)))
        return list(cursor)

    def update_metadata(
        self,
        *,
        tenant_id: str | UUID,
        role_id: str | UUID,
        version: int,
        metadata: Mapping[str, Any],
        tags: Optional[list[str]] = None,
    ) -> Optional[dict[str, Any]]:
        """Replace metadata (and optional tags) on an existing document."""
        update: MutableMapping[str, Any] = {
            "metadata": dict(metadata),
            "updated_at": _utcnow(),
        }
        if tags is not None:
            update["tags"] = list(tags)
        return self._collection.find_one_and_update(
            {
                "tenant_id": _as_uuid_str(tenant_id),
                "role_id": _as_uuid_str(role_id),
                "version": _require_positive_version(version),
            },
            {"$set": update},
            return_document=ReturnDocument.AFTER,
        )

    def append_audit_entry(
        self,
        *,
        tenant_id: str | UUID,
        role_id: str | UUID,
        version: int,
        action: str,
        actor_id: Optional[str | UUID] = None,
        detail: Optional[Mapping[str, Any]] = None,
    ) -> UpdateResult:
        """Append a flexible audit blob to the role meta document."""
        entry = {
            "action": action,
            "at": _utcnow(),
            "actor_id": _as_uuid_str(actor_id) if actor_id is not None else None,
            "detail": dict(detail or {}),
        }
        return self._collection.update_one(
            {
                "tenant_id": _as_uuid_str(tenant_id),
                "role_id": _as_uuid_str(role_id),
                "version": _require_positive_version(version),
            },
            {
                "$push": {"audit_entries": entry},
                "$set": {"updated_at": _utcnow()},
            },
        )

    def delete(
        self,
        *,
        tenant_id: str | UUID,
        role_id: str | UUID,
        version: int,
    ) -> DeleteResult:
        """Delete a role meta document (tenant-scoped)."""
        return self._collection.delete_one(
            {
                "tenant_id": _as_uuid_str(tenant_id),
                "role_id": _as_uuid_str(role_id),
                "version": _require_positive_version(version),
            }
        )
