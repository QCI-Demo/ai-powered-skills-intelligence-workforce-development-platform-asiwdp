"""In-memory transactional tenant store (used for tests and local runs)."""

from __future__ import annotations

import copy
import hashlib
import json
import threading
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from asiwdp_tenant_provisioning.models import (
    IdempotencyRecord,
    ProvisionedTenant,
    TenantConfiguration,
    TenantMetadataEntry,
    TenantRecord,
    build_default_config_blob,
    utcnow,
)


class ConflictError(Exception):
    """Raised when a unique constraint would be violated."""


class IdempotencyConflictError(Exception):
    """Same Idempotency-Key with a different payload hash."""


class InMemoryTenantStore:
    """
    Thread-safe in-memory database for tenant provisioning.

    Mirrors PostgreSQL tables: tenant, tenant_configuration, tenant_metadata,
    idempotency_record. All tenant-owned rows are keyed by tenant_id.
    """

    def __init__(self, *, idempotency_ttl_hours: int = 24) -> None:
        self._lock = threading.RLock()
        self._tenants: dict[UUID, TenantRecord] = {}
        self._slugs: dict[str, UUID] = {}
        self._configurations: dict[UUID, TenantConfiguration] = {}
        self._metadata: dict[UUID, list[TenantMetadataEntry]] = {}
        self._idempotency: dict[str, IdempotencyRecord] = {}
        self._idempotency_ttl = timedelta(hours=idempotency_ttl_hours)

    def reset(self) -> None:
        with self._lock:
            self._tenants.clear()
            self._slugs.clear()
            self._configurations.clear()
            self._metadata.clear()
            self._idempotency.clear()

    @staticmethod
    def hash_request(payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def get_idempotency(self, key: str) -> IdempotencyRecord | None:
        with self._lock:
            record = self._idempotency.get(key)
            if record is None:
                return None
            if record.expires_at <= utcnow():
                del self._idempotency[key]
                return None
            return copy.deepcopy(record)

    def get_tenant(self, tenant_id: UUID) -> TenantRecord | None:
        with self._lock:
            tenant = self._tenants.get(tenant_id)
            return copy.deepcopy(tenant) if tenant else None

    def list_tenants(self) -> list[TenantRecord]:
        with self._lock:
            return [copy.deepcopy(t) for t in self._tenants.values()]

    def get_configuration(self, tenant_id: UUID) -> TenantConfiguration | None:
        with self._lock:
            cfg = self._configurations.get(tenant_id)
            return copy.deepcopy(cfg) if cfg else None

    def get_metadata(self, tenant_id: UUID) -> list[TenantMetadataEntry]:
        with self._lock:
            return [copy.deepcopy(m) for m in self._metadata.get(tenant_id, [])]

    def tenants_for_isolation_check(self, tenant_id: UUID) -> dict[str, Any]:
        """Return only rows belonging to tenant_id (cross-tenant isolation helper)."""
        with self._lock:
            return {
                "tenant": copy.deepcopy(self._tenants.get(tenant_id)),
                "configuration": copy.deepcopy(self._configurations.get(tenant_id)),
                "metadata": [
                    copy.deepcopy(m) for m in self._metadata.get(tenant_id, [])
                ],
                "foreign_tenant_ids": sorted(
                    str(tid) for tid in self._tenants if tid != tenant_id
                ),
            }

    def provision(
        self,
        *,
        slug: str,
        display_name: str,
        plan_code: str,
        data_residency: str,
        created_by: UUID | None,
        configuration_overrides: dict[str, Any] | None,
        metadata: dict[str, Any],
        idempotency_key: str,
        request_hash: str,
    ) -> ProvisionedTenant:
        """
        Atomically create tenant + default configuration + metadata + idempotency.

        If the idempotency key already exists with the same hash, returns the
        prior response without creating a duplicate tenant.
        """
        with self._lock:
            existing = self._idempotency.get(idempotency_key)
            now = utcnow()
            if existing is not None and existing.expires_at > now:
                if existing.request_hash != request_hash:
                    raise IdempotencyConflictError(
                        "Idempotency-Key was reused with a different request body"
                    )
                tenant = self._tenants[existing.tenant_id]
                cfg = self._configurations[existing.tenant_id]
                meta = list(self._metadata.get(existing.tenant_id, []))
                return ProvisionedTenant(
                    tenant=copy.deepcopy(tenant),
                    configuration=copy.deepcopy(cfg),
                    metadata=[copy.deepcopy(m) for m in meta],
                    created=False,
                )

            if slug in self._slugs:
                raise ConflictError(f"Tenant slug '{slug}' already exists")

            tenant_id = uuid4()
            stamp = now
            tenant = TenantRecord(
                tenant_id=tenant_id,
                slug=slug,
                display_name=display_name,
                status="active",
                plan_code=plan_code,
                data_residency=data_residency,
                created_by=created_by,
                created_at=stamp,
                updated_at=stamp,
                provisioned_at=stamp,
            )

            overrides = configuration_overrides or {}
            blob = build_default_config_blob(
                locale=str(overrides.get("locale") or "en-US"),
                timezone_name=str(overrides.get("timezone") or "UTC"),
                overrides={
                    "features": overrides.get("features"),
                    "privacy": overrides.get("privacy"),
                },
            )
            if overrides.get("metering_enabled") is not None:
                blob["metering_enabled"] = bool(overrides["metering_enabled"])
            if overrides.get("gdpr_enabled") is not None:
                blob["gdpr_enabled"] = bool(overrides["gdpr_enabled"])
            if overrides.get("ccpa_enabled") is not None:
                blob["ccpa_enabled"] = bool(overrides["ccpa_enabled"])

            configuration = TenantConfiguration(
                tenant_id=tenant_id,
                defaults=blob["defaults"],
                locale=blob["locale"],
                timezone=blob["timezone"],
                metering_enabled=blob["metering_enabled"],
                gdpr_enabled=blob["gdpr_enabled"],
                ccpa_enabled=blob["ccpa_enabled"],
                schema_version=blob["schema_version"],
                created_at=stamp,
                updated_at=stamp,
            )

            meta_entries: list[TenantMetadataEntry] = []
            for key, value in metadata.items():
                meta_value = value if isinstance(value, dict) else {"value": value}
                meta_entries.append(
                    TenantMetadataEntry(
                        id=uuid4(),
                        tenant_id=tenant_id,
                        meta_key=key,
                        meta_value=meta_value,
                        created_by=str(created_by) if created_by else None,
                        created_at=stamp,
                        updated_at=stamp,
                    )
                )

            # Commit all rows atomically under the lock
            self._tenants[tenant_id] = tenant
            self._slugs[slug] = tenant_id
            self._configurations[tenant_id] = configuration
            self._metadata[tenant_id] = meta_entries

            result = ProvisionedTenant(
                tenant=copy.deepcopy(tenant),
                configuration=copy.deepcopy(configuration),
                metadata=[copy.deepcopy(m) for m in meta_entries],
                created=True,
            )
            body = result.to_response_dict()
            self._idempotency[idempotency_key] = IdempotencyRecord(
                idempotency_key=idempotency_key,
                tenant_id=tenant_id,
                request_hash=request_hash,
                response_status=201,
                response_body=body,
                created_at=stamp,
                expires_at=stamp + self._idempotency_ttl,
            )
            return result
