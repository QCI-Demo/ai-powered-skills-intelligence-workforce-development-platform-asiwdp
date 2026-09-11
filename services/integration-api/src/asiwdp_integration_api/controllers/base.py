"""Shared controller helpers for tenant-scoped integration exchange."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from asiwdp_auth import TenantContext
from fastapi import HTTPException, status


class TenantScopedController:
    """Base controller enforcing JWT tenant isolation on payload tenantId."""

    api_version: str = "v1"

    def ensure_tenant(
        self,
        context: TenantContext,
        payload_tenant_id: UUID | str | None,
    ) -> str:
        tenant_id = context.tenant_id
        if payload_tenant_id is None:
            return tenant_id
        payload = str(payload_tenant_id)
        if payload != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "tenant_mismatch",
                    "message": "Payload tenantId does not match authenticated tenant",
                },
            )
        return tenant_id

    def ack(
        self,
        *,
        context: TenantContext,
        resource: str,
        source_record_id: str | None = None,
        message: str = "accepted",
    ) -> dict[str, Any]:
        return {
            "accepted": True,
            "apiVersion": self.api_version,
            "tenantId": context.tenant_id,
            "resource": resource,
            "sourceRecordId": source_record_id,
            "message": message,
        }

    def batch_ack(
        self,
        *,
        context: TenantContext,
        resource: str,
        accepted_count: int,
        correlation_id: str | None,
        status_href: str,
    ) -> dict[str, Any]:
        return {
            "accepted": True,
            "apiVersion": self.api_version,
            "tenantId": context.tenant_id,
            "resource": resource,
            "correlationId": correlation_id,
            "acceptedCount": accepted_count,
            "statusHref": status_href,
            "message": "batch accepted",
        }
