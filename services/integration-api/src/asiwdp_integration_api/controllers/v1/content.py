"""v1 content-provider integration controller."""

from __future__ import annotations

from typing import Any

from asiwdp_auth import TenantContext

from asiwdp_integration_api.controllers.base import TenantScopedController
from asiwdp_integration_api.schemas.models import (
    ContentCatalogRecord,
    CredentialRotateRequest,
)


class ContentV1Controller(TenantScopedController):
    api_version = "v1"

    def upsert_catalog(
        self, context: TenantContext, record: ContentCatalogRecord
    ) -> dict[str, Any]:
        self.ensure_tenant(context, record.tenant_id)
        return self.ack(
            context=context,
            resource="content.catalog",
            source_record_id=record.source_record_id,
            message="catalog record accepted",
        )

    def rotate_credential(
        self, context: TenantContext, body: CredentialRotateRequest
    ) -> dict[str, Any]:
        # Opaque credentialRef only — never accept or echo secret material.
        return {
            "rotated": True,
            "provider": body.provider,
            "credentialRef": body.credential_ref,
            "apiVersion": self.api_version,
            "tenantId": context.tenant_id,
            "message": "rotation scheduled in secret manager",
        }
