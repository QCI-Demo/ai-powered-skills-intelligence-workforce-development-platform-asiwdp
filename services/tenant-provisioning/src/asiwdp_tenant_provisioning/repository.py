"""In-memory / SQLite repository with atomic tenant + config persistence."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator
from uuid import UUID, uuid4

from asiwdp_tenant_provisioning.models import (
    ConfigurationRecord,
    IdempotencyRecord,
    MetadataRecord,
    TenantRecord,
    utcnow,
)

_DDL = """
CREATE TABLE IF NOT EXISTS tenant (
    tenant_id        TEXT PRIMARY KEY,
    slug             TEXT NOT NULL UNIQUE,
    display_name     TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'active',
    plan_code        TEXT NOT NULL DEFAULT 'standard',
    region           TEXT NOT NULL DEFAULT 'us-east-1',
    timezone         TEXT NOT NULL DEFAULT 'UTC',
    contact          TEXT NOT NULL DEFAULT '{}',
    provisioned_at   TEXT NOT NULL,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    created_by       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tenant_configuration (
    id            TEXT PRIMARY KEY,
    tenant_id     TEXT NOT NULL,
    config_key    TEXT NOT NULL,
    config_value  TEXT NOT NULL,
    is_default    INTEGER NOT NULL DEFAULT 1,
    version       INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    UNIQUE (tenant_id, config_key),
    FOREIGN KEY (tenant_id) REFERENCES tenant (tenant_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tenant_configuration_tenant_id
    ON tenant_configuration (tenant_id);

CREATE TABLE IF NOT EXISTS tenant_metadata (
    id          TEXT PRIMARY KEY,
    tenant_id   TEXT NOT NULL,
    meta_key    TEXT NOT NULL,
    meta_value  TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    UNIQUE (tenant_id, meta_key),
    FOREIGN KEY (tenant_id) REFERENCES tenant (tenant_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tenant_metadata_tenant_id
    ON tenant_metadata (tenant_id);

CREATE TABLE IF NOT EXISTS idempotency_record (
    id                    TEXT PRIMARY KEY,
    idempotency_key       TEXT NOT NULL UNIQUE,
    requesting_tenant_id  TEXT,
    created_tenant_id     TEXT NOT NULL,
    request_hash          TEXT NOT NULL,
    response_status       INTEGER NOT NULL,
    response_body         TEXT NOT NULL,
    created_at            TEXT NOT NULL,
    expires_at            TEXT NOT NULL,
    FOREIGN KEY (created_tenant_id) REFERENCES tenant (tenant_id) ON DELETE CASCADE
);
"""


def _dt_to_str(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _str_to_dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


class TenantRepository:
    """SQLite-backed repository (in-memory for tests; file path for local runs)."""

    def __init__(self, database_url: str = ":memory:") -> None:
        self._database_url = database_url
        self._lock = threading.RLock()
        # Shared connection for :memory: so schema persists across connections
        self._shared: sqlite3.Connection | None = None
        if database_url == ":memory:":
            self._shared = sqlite3.connect(
                ":memory:", check_same_thread=False, isolation_level=None
            )
            self._shared.row_factory = sqlite3.Row
            self._shared.execute("PRAGMA foreign_keys = ON")
            self._shared.executescript(_DDL)

    def _connect(self) -> sqlite3.Connection:
        if self._shared is not None:
            return self._shared
        conn = sqlite3.connect(
            self._database_url, check_same_thread=False, isolation_level=None
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(_DDL)
        return conn

    @contextmanager
    def _cursor(self) -> Iterator[sqlite3.Cursor]:
        with self._lock:
            conn = self._connect()
            cur = conn.cursor()
            try:
                yield cur
            finally:
                cur.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Cursor]:
        with self._lock:
            conn = self._connect()
            cur = conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            try:
                yield cur
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                cur.close()

    def get_idempotency(self, key: str) -> IdempotencyRecord | None:
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM idempotency_record WHERE idempotency_key = ?",
                (key,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_idempotency(row)

    def get_tenant(self, tenant_id: UUID) -> TenantRecord | None:
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM tenant WHERE tenant_id = ?",
                (str(tenant_id),),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_tenant(row)

    def get_tenant_by_slug(self, slug: str) -> TenantRecord | None:
        with self._cursor() as cur:
            cur.execute("SELECT * FROM tenant WHERE slug = ?", (slug,))
            row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_tenant(row)

    def list_configuration(self, tenant_id: UUID) -> list[ConfigurationRecord]:
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM tenant_configuration WHERE tenant_id = ? ORDER BY config_key",
                (str(tenant_id),),
            )
            rows = cur.fetchall()
        return [self._row_to_config(r) for r in rows]

    def list_metadata(self, tenant_id: UUID) -> list[MetadataRecord]:
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM tenant_metadata WHERE tenant_id = ? ORDER BY meta_key",
                (str(tenant_id),),
            )
            rows = cur.fetchall()
        return [self._row_to_metadata(r) for r in rows]

    def list_tenants_for_isolation_check(self) -> list[TenantRecord]:
        with self._cursor() as cur:
            cur.execute("SELECT * FROM tenant ORDER BY created_at")
            rows = cur.fetchall()
        return [self._row_to_tenant(r) for r in rows]

    def create_tenant_atomic(
        self,
        *,
        slug: str,
        display_name: str,
        plan_code: str,
        region: str,
        timezone_name: str,
        contact: dict[str, Any],
        created_by: str,
        default_config: dict[str, Any],
        metadata: dict[str, Any],
        idempotency_key: str | None,
        requesting_tenant_id: UUID | None,
        request_hash: str,
        response_builder: Any,
        idempotency_ttl_hours: int = 24,
    ) -> tuple[TenantRecord, list[ConfigurationRecord], list[MetadataRecord], bool]:
        """Persist tenant + defaults + optional idempotency row atomically.

        Returns (tenant, configs, metadata, created_flag).
        """
        now = utcnow()
        tenant_id = uuid4()

        with self.transaction() as cur:
            if idempotency_key:
                cur.execute(
                    "SELECT * FROM idempotency_record WHERE idempotency_key = ?",
                    (idempotency_key,),
                )
                existing = cur.fetchone()
                if existing is not None:
                    record = self._row_to_idempotency(existing)
                    if record.request_hash != request_hash:
                        raise ConflictError(
                            "Idempotency-Key reuse with a different request body"
                        )
                    cur.execute(
                        "SELECT * FROM tenant WHERE tenant_id = ?",
                        (str(record.created_tenant_id),),
                    )
                    tenant_row = cur.fetchone()
                    if tenant_row is None:
                        raise ConflictError("Idempotency record references missing tenant")
                    tenant = self._row_to_tenant(tenant_row)
                    cur.execute(
                        "SELECT * FROM tenant_configuration WHERE tenant_id = ?",
                        (str(tenant.tenant_id),),
                    )
                    configs = [self._row_to_config(r) for r in cur.fetchall()]
                    cur.execute(
                        "SELECT * FROM tenant_metadata WHERE tenant_id = ?",
                        (str(tenant.tenant_id),),
                    )
                    metas = [self._row_to_metadata(r) for r in cur.fetchall()]
                    return tenant, configs, metas, False

            cur.execute("SELECT 1 FROM tenant WHERE slug = ?", (slug,))
            if cur.fetchone() is not None:
                raise ConflictError(f"Tenant slug '{slug}' already exists")

            cur.execute(
                """
                INSERT INTO tenant (
                    tenant_id, slug, display_name, status, plan_code, region,
                    timezone, contact, provisioned_at, created_at, updated_at, created_by
                ) VALUES (?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(tenant_id),
                    slug,
                    display_name,
                    plan_code,
                    region,
                    timezone_name,
                    json.dumps(contact),
                    _dt_to_str(now),
                    _dt_to_str(now),
                    _dt_to_str(now),
                    created_by,
                ),
            )

            configs: list[ConfigurationRecord] = []
            for key, value in default_config.items():
                cfg_id = uuid4()
                cur.execute(
                    """
                    INSERT INTO tenant_configuration (
                        id, tenant_id, config_key, config_value, is_default,
                        version, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, 1, 1, ?, ?)
                    """,
                    (
                        str(cfg_id),
                        str(tenant_id),
                        key,
                        json.dumps(value),
                        _dt_to_str(now),
                        _dt_to_str(now),
                    ),
                )
                configs.append(
                    ConfigurationRecord(
                        id=cfg_id,
                        tenant_id=tenant_id,
                        config_key=key,
                        config_value=value,
                        is_default=True,
                        version=1,
                        created_at=now,
                        updated_at=now,
                    )
                )

            metas: list[MetadataRecord] = []
            for key, value in metadata.items():
                meta_id = uuid4()
                meta_value = value if isinstance(value, dict) else {"value": value}
                cur.execute(
                    """
                    INSERT INTO tenant_metadata (
                        id, tenant_id, meta_key, meta_value, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(meta_id),
                        str(tenant_id),
                        key,
                        json.dumps(meta_value),
                        _dt_to_str(now),
                        _dt_to_str(now),
                    ),
                )
                metas.append(
                    MetadataRecord(
                        id=meta_id,
                        tenant_id=tenant_id,
                        meta_key=key,
                        meta_value=meta_value,
                        created_at=now,
                        updated_at=now,
                    )
                )

            tenant = TenantRecord(
                tenant_id=tenant_id,
                slug=slug,
                display_name=display_name,
                status="active",
                plan_code=plan_code,
                region=region,
                timezone=timezone_name,
                contact=contact,
                provisioned_at=now,
                created_at=now,
                updated_at=now,
                created_by=created_by,
            )

            if idempotency_key:
                response_body = response_builder(tenant, configs, metas, False)
                expires = now + timedelta(hours=idempotency_ttl_hours)
                cur.execute(
                    """
                    INSERT INTO idempotency_record (
                        id, idempotency_key, requesting_tenant_id, created_tenant_id,
                        request_hash, response_status, response_body, created_at, expires_at
                    ) VALUES (?, ?, ?, ?, ?, 201, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        idempotency_key,
                        str(requesting_tenant_id) if requesting_tenant_id else None,
                        str(tenant_id),
                        request_hash,
                        json.dumps(response_body),
                        _dt_to_str(now),
                        _dt_to_str(expires),
                    ),
                )

            return tenant, configs, metas, True

    @staticmethod
    def _row_to_tenant(row: sqlite3.Row) -> TenantRecord:
        return TenantRecord(
            tenant_id=UUID(row["tenant_id"]),
            slug=row["slug"],
            display_name=row["display_name"],
            status=row["status"],
            plan_code=row["plan_code"],
            region=row["region"],
            timezone=row["timezone"],
            contact=json.loads(row["contact"]),
            provisioned_at=_str_to_dt(row["provisioned_at"]),
            created_at=_str_to_dt(row["created_at"]),
            updated_at=_str_to_dt(row["updated_at"]),
            created_by=row["created_by"],
        )

    @staticmethod
    def _row_to_config(row: sqlite3.Row) -> ConfigurationRecord:
        return ConfigurationRecord(
            id=UUID(row["id"]),
            tenant_id=UUID(row["tenant_id"]),
            config_key=row["config_key"],
            config_value=json.loads(row["config_value"]),
            is_default=bool(row["is_default"]),
            version=int(row["version"]),
            created_at=_str_to_dt(row["created_at"]),
            updated_at=_str_to_dt(row["updated_at"]),
        )

    @staticmethod
    def _row_to_metadata(row: sqlite3.Row) -> MetadataRecord:
        return MetadataRecord(
            id=UUID(row["id"]),
            tenant_id=UUID(row["tenant_id"]),
            meta_key=row["meta_key"],
            meta_value=json.loads(row["meta_value"]),
            created_at=_str_to_dt(row["created_at"]),
            updated_at=_str_to_dt(row["updated_at"]),
        )

    @staticmethod
    def _row_to_idempotency(row: sqlite3.Row) -> IdempotencyRecord:
        req = row["requesting_tenant_id"]
        return IdempotencyRecord(
            id=UUID(row["id"]),
            idempotency_key=row["idempotency_key"],
            requesting_tenant_id=UUID(req) if req else None,
            created_tenant_id=UUID(row["created_tenant_id"]),
            request_hash=row["request_hash"],
            response_status=int(row["response_status"]),
            response_body=json.loads(row["response_body"]),
            created_at=_str_to_dt(row["created_at"]),
            expires_at=_str_to_dt(row["expires_at"]),
        )


class ConflictError(Exception):
    """Raised when an idempotency or uniqueness conflict occurs."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
