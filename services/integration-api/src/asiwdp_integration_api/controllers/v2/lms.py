"""v2 LMS integration controller (batch activities)."""

from __future__ import annotations

from typing import Any

from asiwdp_auth import TenantContext

from asiwdp_integration_api.controllers.base import TenantScopedController
from asiwdp_integration_api.schemas.models import BatchRequest, LearnerActivityRecord


class LmsV2Controller(TenantScopedController):
    api_version = "v2"

    def ingest_activity_batch(
        self, context: TenantContext, batch: BatchRequest
    ) -> dict[str, Any]:
        accepted = 0
        for raw in batch.records:
            record = LearnerActivityRecord.model_validate(raw)
            self.ensure_tenant(context, record.tenant_id)
            accepted += 1
        correlation = batch.correlation_id or f"lms-batch-{context.tenant_id[:8]}"
        return self.batch_ack(
            context=context,
            resource="lms.learner_activity",
            accepted_count=accepted,
            correlation_id=correlation,
            status_href=f"/api/v2/lms/activities/batches/{correlation}/status",
        )
