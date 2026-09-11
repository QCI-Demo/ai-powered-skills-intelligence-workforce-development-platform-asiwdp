"""v1 LMS integration controller."""

from __future__ import annotations

from typing import Any

from asiwdp_auth import TenantContext

from asiwdp_integration_api.controllers.base import TenantScopedController
from asiwdp_integration_api.schemas.models import LearnerActivityRecord


class LmsV1Controller(TenantScopedController):
    api_version = "v1"

    def ingest_activity(
        self, context: TenantContext, record: LearnerActivityRecord
    ) -> dict[str, Any]:
        self.ensure_tenant(context, record.tenant_id)
        return self.ack(
            context=context,
            resource="lms.learner_activity",
            source_record_id=record.source_record_id,
            message="learner activity accepted",
        )

    def list_content(self, context: TenantContext) -> dict[str, Any]:
        return {
            "apiVersion": self.api_version,
            "tenantId": context.tenant_id,
            "items": [],
            "count": 0,
        }
