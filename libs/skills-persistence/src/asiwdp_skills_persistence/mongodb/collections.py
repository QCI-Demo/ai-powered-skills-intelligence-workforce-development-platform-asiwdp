"""MongoDB collection definitions with JSON Schema validators."""

from __future__ import annotations

from typing import Any

from pymongo.database import Database
from pymongo.errors import CollectionInvalid, OperationFailure

SKILL_META_COLLECTION = "skill_meta"
ROLE_META_COLLECTION = "role_meta"

_UUID_PATTERN = (
    "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    "[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

_AUDIT_ENTRY_SCHEMA: dict[str, Any] = {
    "bsonType": "object",
    "required": ["action", "at"],
    "properties": {
        "action": {"bsonType": "string"},
        "at": {"bsonType": "date"},
        "actor_id": {"bsonType": ["string", "null"]},
        "detail": {"bsonType": "object"},
    },
}


def skill_meta_validator() -> dict[str, Any]:
    """Return the JSON Schema validator document for ``skill_meta``."""
    return {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["tenant_id", "skill_id", "version"],
            "properties": {
                "_id": {"bsonType": ["objectId", "string"]},
                "tenant_id": {
                    "bsonType": "string",
                    "pattern": _UUID_PATTERN,
                },
                "skill_id": {
                    "bsonType": "string",
                    "pattern": _UUID_PATTERN,
                },
                "version": {"bsonType": "int", "minimum": 1},
                "metadata": {"bsonType": "object"},
                "tags": {
                    "bsonType": "array",
                    "items": {"bsonType": "string"},
                },
                "audit_entries": {
                    "bsonType": "array",
                    "items": _AUDIT_ENTRY_SCHEMA,
                },
                "created_at": {"bsonType": "date"},
                "updated_at": {"bsonType": "date"},
            },
            "additionalProperties": False,
        }
    }


def role_meta_validator() -> dict[str, Any]:
    """Return the JSON Schema validator document for ``role_meta``."""
    return {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["tenant_id", "role_id", "version"],
            "properties": {
                "_id": {"bsonType": ["objectId", "string"]},
                "tenant_id": {
                    "bsonType": "string",
                    "pattern": _UUID_PATTERN,
                },
                "role_id": {
                    "bsonType": "string",
                    "pattern": _UUID_PATTERN,
                },
                "version": {"bsonType": "int", "minimum": 1},
                "metadata": {"bsonType": "object"},
                "tags": {
                    "bsonType": "array",
                    "items": {"bsonType": "string"},
                },
                "audit_entries": {
                    "bsonType": "array",
                    "items": _AUDIT_ENTRY_SCHEMA,
                },
                "created_at": {"bsonType": "date"},
                "updated_at": {"bsonType": "date"},
            },
            "additionalProperties": False,
        }
    }


def _ensure_collection(
    db: Database,
    name: str,
    validator: dict[str, Any],
) -> None:
    """Create or update a collection with the given validator."""
    try:
        db.create_collection(
            name,
            validator=validator,
            validationLevel="moderate",
            validationAction="error",
        )
        return
    except CollectionInvalid:
        try:
            db.command(
                {
                    "collMod": name,
                    "validator": validator,
                    "validationLevel": "moderate",
                    "validationAction": "error",
                }
            )
            return
        except (OperationFailure, NotImplementedError, TypeError):
            # Collection exists; validator update unsupported in this driver/mock.
            return
    except (OperationFailure, NotImplementedError, TypeError):
        # Validator options unsupported (e.g. mongomock): ensure bare collection.
        if name not in db.list_collection_names():
            db.create_collection(name)


def ensure_meta_collections(db: Database) -> None:
    """Idempotently create ``skill_meta`` / ``role_meta`` with indexes."""
    _ensure_collection(db, SKILL_META_COLLECTION, skill_meta_validator())
    _ensure_collection(db, ROLE_META_COLLECTION, role_meta_validator())

    skill_meta = db[SKILL_META_COLLECTION]
    skill_meta.create_index(
        [("tenant_id", 1), ("skill_id", 1), ("version", 1)],
        unique=True,
        name="uq_skill_meta_tenant_skill_version",
    )
    skill_meta.create_index(
        [("tenant_id", 1), ("version", 1)],
        name="idx_skill_meta_tenant_version",
    )

    role_meta = db[ROLE_META_COLLECTION]
    role_meta.create_index(
        [("tenant_id", 1), ("role_id", 1), ("version", 1)],
        unique=True,
        name="uq_role_meta_tenant_role_version",
    )
    role_meta.create_index(
        [("tenant_id", 1), ("version", 1)],
        name="idx_role_meta_tenant_version",
    )
